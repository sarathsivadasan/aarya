# -*- coding: utf-8 -*-

import base64
import io
import json
import logging
import re

import requests

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

BOOKING_CANDIDATES = (
    'odex.booking', 'odex.workshop.booking', 'workshop.booking',
    'odex.booking.booking', 'garage.booking',
)
BOOKING_EXCLUDE = ('slot', 'schedule', 'break', 'offday', 'line', 'wizard')

VIN_RE = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b')
PLATE_RE = re.compile(r'\b([A-Z]{1,3})[\s/-]?(\d{1,6})\b')


class GatePassScan(models.Model):
    _inherit = 'fleet.gate.pass'

    booking_res_id = fields.Integer(string="Booking Record ID", copy=False,
                                    index=True)

    # ==================================================================
    # Booking bridge (model resolved at runtime — survives any rename)
    # ==================================================================
    @api.model
    def _booking_model(self):
        for name in BOOKING_CANDIDATES:
            if name in self.env:
                return name
        found = self.env['ir.model'].sudo().search(
            [('model', 'like', '%booking%'), ('transient', '=', False)])
        for m in found:
            if not any(x in m.model for x in BOOKING_EXCLUDE) \
                    and m.model in self.env:
                return m.model
        return False

    def _booking_record(self):
        self.ensure_one()
        model = self._booking_model()
        if not model or not self.booking_res_id:
            return None
        rec = self.env[model].browse(self.booking_res_id)
        return rec if rec.exists() else None

    @api.model
    def _booking_info(self, rec):
        if not rec:
            return False

        def g(*names):
            for n in names:
                v = getattr(rec, n, False)
                if v:
                    return v
            return False

        state = g('state', 'status')
        if state and rec._fields.get('state') \
                and rec._fields['state'].type == 'selection':
            sel = dict(rec._fields['state']._description_selection(self.env))
            state = sel.get(state, state)
        advisor = g('advisor_id', 'service_advisor_id', 'user_id')
        services = g('requested_services', 'service_ids', 'note')
        if hasattr(services, 'mapped'):
            services = ", ".join(services.mapped('display_name'))
        return {
            'id': rec.id,
            'model': rec._name,
            'name': rec.display_name,
            'state': state or '',
            'date': g('booking_date', 'date', 'appointment_date') or False,
            'advisor': advisor.display_name if advisor else '',
            'services': services or '',
        }

    @api.model
    def booking_search(self, term):
        """name_search proxy on the detected booking model."""
        model = self._booking_model()
        if not model:
            return {'model': False, 'results': []}
        results = self.env[model].name_search(term or '', limit=8)
        return {'model': model,
                'results': [{'id': i, 'name': n} for i, n in results]}

    def action_open_booking(self):
        self.ensure_one()
        rec = self._booking_record()
        if not rec:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': rec._name,
            'res_id': rec.id,
            'view_mode': 'form',
        }

    def _auto_link_booking(self):
        """Link an open booking of the same vehicle/customer on create."""
        model = self._booking_model()
        if not model:
            return
        Booking = self.env[model]
        for rec in self.filtered(lambda r: not r.booking_res_id):
            domain = []
            if 'vehicle_id' in Booking._fields and rec.vehicle_id:
                domain.append(('vehicle_id', '=', rec.vehicle_id.id))
            elif 'partner_id' in Booking._fields and rec.partner_id:
                domain.append(('partner_id', '=', rec.partner_id.id))
            if not domain:
                continue
            if 'state' in Booking._fields:
                domain.append(('state', 'not in',
                               ('cancelled', 'cancel', 'no_show', 'done',
                                'completed')))
            booking = Booking.search(domain, order='id desc', limit=1)
            if booking:
                rec.booking_res_id = booking.id
                if not rec.booking_ref:
                    rec.booking_ref = booking.display_name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            records._auto_link_booking()
        except Exception:
            _logger.exception("Gate pass booking auto-link failed")
        return records

    # ==================================================================
    # OCR: registration plate / Mulkiya  →  fleet data
    # ==================================================================
    @api.model
    def _ocr_text(self, image_b64):
        """Extract raw text. Local pytesseract first, then the endpoint
        configured in Settings (odex_gatepass.ocr_endpoint /
        odex_gatepass.ocr_key)."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(base64.b64decode(image_b64)))
            return pytesseract.image_to_string(img)
        except Exception:
            pass
        icp = self.env['ir.config_parameter'].sudo()
        endpoint = icp.get_param('odex_gatepass.ocr_endpoint')
        if endpoint:
            try:
                resp = requests.post(
                    endpoint,
                    json={'image': image_b64},
                    headers={'Authorization': icp.get_param(
                        'odex_gatepass.ocr_key') or ''},
                    timeout=20)
                resp.raise_for_status()
                data = resp.json()
                return data.get('text') or json.dumps(data)
            except Exception:
                _logger.exception("External OCR endpoint failed")
        return None

    @api.model
    def ocr_scan(self, image_b64, scan_type):
        """scan_type: 'plate' (registration) or 'mulkiya' (chassis/VIN)."""
        text = self._ocr_text(image_b64)
        if text is None:
            return {'error': _(
                "No OCR engine available. Install pytesseract on the "
                "server or set System Parameter odex_gatepass.ocr_endpoint.")}
        text_up = text.upper()
        result = {'text': text}

        vin = VIN_RE.search(text_up.replace(' ', ''))
        if vin:
            result['vin'] = vin.group(0)
        plate = PLATE_RE.search(text_up)
        if plate:
            result['registration_no'] = "%s %s" % (
                plate.group(1), plate.group(2))
        if scan_type == 'mulkiya':
            for label, key in (('OWNER', 'owner'), ('EXP', 'expiry')):
                m = re.search(label + r'[^A-Z0-9]*([A-Z0-9 /.-]{4,40})',
                              text_up)
                if m:
                    result[key] = m.group(1).strip()

        # Fleet lookup — rest of the data comes from the vehicle record
        vehicle = self._fleet_lookup(result.get('registration_no'),
                                     result.get('vin'))
        if vehicle:
            result['vehicle'] = vehicle
        return result

    @api.model
    def _fleet_lookup(self, plate=None, vin=None):
        Vehicle = self.env['fleet.vehicle']
        vehicle = None
        if vin:
            vehicle = Vehicle.search([('vin_sn', '=ilike', vin)], limit=1)
        if not vehicle and plate:
            compact = plate.replace(' ', '').replace('-', '')
            vehicle = Vehicle.search(
                ['|', ('license_plate', '=ilike', plate),
                 ('license_plate', '=ilike', compact)], limit=1)
        if not vehicle:
            return False
        return {
            'id': vehicle.id,
            'name': vehicle.display_name,
            'registration_no': vehicle.license_plate or '',
            'vin': vehicle.vin_sn or '',
            'partner_id': {'id': vehicle.partner_id.id,
                           'name': vehicle.partner_id.display_name}
            if getattr(vehicle, 'partner_id', False) else False,
        }

    @api.model
    def vin_decode(self, vin):
        """Best-effort VIN decode via the free NHTSA vPIC API."""
        if not vin or len(vin) != 17:
            return {'error': _("VIN must be 17 characters.")}
        try:
            resp = requests.get(
                "https://vpic.nhtsa.dot.gov/api/vehicles/"
                "DecodeVinValues/%s?format=json" % vin, timeout=15)
            resp.raise_for_status()
            row = (resp.json().get('Results') or [{}])[0]
            return {k: v for k, v in {
                'brand': row.get('Make') or '',
                'model': row.get('Model') or '',
                'manufacturing_year': row.get('ModelYear') or '',
                'fuel': row.get('FuelTypePrimary') or '',
                'transmission': row.get('TransmissionStyle') or '',
                'engine_capacity': row.get('DisplacementL') or '',
            }.items() if v}
        except Exception:
            _logger.exception("VIN decode failed")
            return {'error': _("VIN decode service unreachable.")}
