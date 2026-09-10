# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # NOTE: emirate / plate_code used to be declared here. They duplicated
    # fleet_emirate_id (fleet.emirates) and fleet_code_id (fleet.characters)
    # from the Odex fleet extension, so they were removed — always read the
    # native fleet fields instead.
    engine_number = fields.Char(string='Engine Number')
    cylinder_count = fields.Integer(string='Cylinders')
    booking_ids = fields.One2many(
        'odex.workshop.booking', 'vehicle_id', string='Bookings')
    booking_count = fields.Integer(compute='_compute_booking_count')

    def _compute_booking_count(self):
        data = dict(self.env['odex.workshop.booking']._read_group(
            [('vehicle_id', 'in', self.ids)], ['vehicle_id'], ['__count']))
        for rec in self:
            rec.booking_count = data.get(rec, 0)

    def action_view_bookings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_workshop_booking.action_workshop_booking')
        action['domain'] = [('vehicle_id', '=', self.id)]
        action['context'] = {'default_vehicle_id': self.id,
                             'default_partner_id': self.driver_id.id}
        return action

    @api.model
    def _find_or_create_from_booking(self, partner, vals):
        """Match by plate/VIN; create only if no match. Owner = partner."""
        plate = (vals.get('license_plate') or '').strip()
        vin = (vals.get('vin_sn') or '').strip()
        domain = []
        if plate:
            domain.append(('license_plate', '=ilike', plate))
        if vin:
            domain = ['|'] + domain + [('vin_sn', '=ilike', vin)] if domain \
                else [('vin_sn', '=ilike', vin)]
        vehicle = self.search(domain, limit=1) if domain else self.browse()
        if vehicle:
            if not vehicle.driver_id:
                vehicle.driver_id = partner.id
            return vehicle
        vals['driver_id'] = partner.id
        return self.create(vals)

    # ------------------------------------------------------------------
    # Plate composition (Emirate / Code / Number)
    # ------------------------------------------------------------------
    # The Odex fleet extension owns these fields. Names differ between
    # installs, so resolve them from the model instead of hardcoding — and
    # read the comodel from the field definition rather than guessing.
    EMIRATE_FIELDS = ['fleet_emirate_id', 'emirate_id', 'emirates_id']
    CODE_FIELDS = ['fleet_code_id', 'plate_code_id', 'code_id',
                   'character_id', 'characters_id']

    @api.model
    def _plate_field(self, candidates):
        """Return (field_name, comodel) for the first candidate that exists."""
        for name in candidates:
            field = self._fields.get(name)
            if field and field.type == 'many2one':
                return name, field.comodel_name
        return None, None

    @api.model
    def _plate_options(self):
        """Selectable Emirates / Codes for the booking form and portal."""
        emirate_field, emirate_model = self._plate_field(self.EMIRATE_FIELDS)
        code_field, code_model = self._plate_field(self.CODE_FIELDS)
        empty = self.env['res.partner'].browse()
        return {
            'emirate_field': emirate_field,
            'code_field': code_field,
            'emirates': self.env[emirate_model].sudo().search([])
            if emirate_model else empty,
            'plate_codes': self.env[code_model].sudo().search([])
            if code_model else empty,
        }

    @api.model
    def _apply_plate_values(self, vals, emirate_id=None, code_id=None):
        """Write the native plate fields, whatever they are called here."""
        emirate_field, _emirate_model = self._plate_field(self.EMIRATE_FIELDS)
        code_field, _code_model = self._plate_field(self.CODE_FIELDS)
        if emirate_field and emirate_id:
            vals[emirate_field] = int(emirate_id)
        if code_field and code_id:
            vals[code_field] = int(code_id)
        return vals

    def _plate_parts(self):
        """(emirate, code, number) for display — never a bare '//1111'."""
        self.ensure_one()
        emirate_field, _m1 = self._plate_field(self.EMIRATE_FIELDS)
        code_field, _m2 = self._plate_field(self.CODE_FIELDS)
        emirate = self[emirate_field].display_name if emirate_field and \
            self[emirate_field] else ''
        code = self[code_field].display_name if code_field and \
            self[code_field] else ''
        return emirate, code, self.license_plate or ''

    def plate_label(self):
        """Human plate string, skipping the parts that are not filled in."""
        self.ensure_one()
        parts = [p for p in self._plate_parts() if p]
        return ' / '.join(parts) if parts else _('No plate')

    # ------------------------------------------------------------------
    # Customer-facing service status
    # ------------------------------------------------------------------
    # Ordered pipeline. Each entry is (key, label, badge tone). The status is
    # derived from records that already exist in the workshop database — no
    # duplicate status field is stored on the vehicle.
    SERVICE_PIPELINE = [
        ('gate_in', 'Gate Pass IN', 'blue'),
        ('inspection_pending', 'Inspection Pending', 'orange'),
        ('inspection_done', 'Inspection Completed', 'blue'),
        ('estimate_pending', 'Estimation Pending', 'orange'),
        ('estimate_sent', 'Estimation Sent', 'purple'),
        ('estimate_approved', 'Estimation Approved', 'green'),
        ('job_open', 'Job Card Open', 'blue'),
        ('in_progress', 'Repair in Progress', 'blue'),
        ('waiting_parts', 'Waiting for Parts', 'orange'),
        ('invoice_ready', 'Invoice Ready', 'purple'),
        ('ready', 'Ready for Delivery', 'green'),
        ('delivered', 'Delivered', 'grey'),
    ]

    def _service_timeline(self):
        """Build the timeline from records that actually exist.

        Only models present in this database are probed, and only stages with
        a real underlying record are returned — nothing is invented.
        """
        self.ensure_one()
        env = self.env
        stages = []

        def add(key, done, reference=None, date=None):
            if not done:
                return
            label, tone = next(
                ((l, t) for k, l, t in self.SERVICE_PIPELINE if k == key),
                (key, 'grey'))
            stages.append({'key': key, 'label': label, 'tone': tone,
                           'reference': reference, 'date': date})

        booking = env['odex.workshop.booking'].sudo().search(
            [('vehicle_id', '=', self.id),
             ('state', 'not in', ('cancelled', 'no_show'))],
            order='booking_date desc', limit=1)
        if booking:
            add('gate_in', booking.state in ('arrived', 'done'),
                booking.name, booking.booking_date)

        for model_name in ('job.card', 'garage.job.card', 'workshop.job.card',
                           'odex.job.card'):
            if model_name in env:
                cards = env[model_name].sudo().search(
                    [('vehicle_id', '=', self.id)], order='id desc', limit=1) \
                    if 'vehicle_id' in env[model_name]._fields else None
                if cards:
                    card = cards[0]
                    add('job_open', True, card.display_name,
                        getattr(card, 'create_date', False))
                break

        if 'sale.order' in env and self.driver_id:
            quote = env['sale.order'].sudo().search(
                [('partner_id', '=', self.driver_id.commercial_partner_id.id)],
                order='id desc', limit=1)
            if quote:
                add('estimate_sent', quote.state in ('sent', 'sale'),
                    quote.name, quote.date_order)
                add('estimate_approved', quote.state == 'sale',
                    quote.name, quote.date_order)

        if self.driver_id:
            invoice = env['account.move'].sudo().search([
                ('partner_id', '=', self.driver_id.commercial_partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ], order='id desc', limit=1)
            if invoice:
                add('invoice_ready', True, invoice.name, invoice.invoice_date)
                add('delivered', invoice.payment_state == 'paid',
                    invoice.name, invoice.invoice_date)

        return stages

    def _service_status(self):
        """Latest reached stage, or None when the vehicle is not in service."""
        self.ensure_one()
        timeline = self._service_timeline()
        return timeline[-1] if timeline else None
