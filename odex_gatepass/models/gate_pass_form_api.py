# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class GatePassFormApi(models.Model):
    _inherit = 'fleet.gate.pass'

    send_whatsapp_notification = fields.Boolean(
        string="Send WhatsApp Notification", default=True)
    send_sms_notification = fields.Boolean(
        string="Send SMS Notification", default=True)
    vehicle_status_override = fields.Selection(
        selection=lambda self: self.env['fleet.gate.pass']._fields[
            'vehicle_status'].selection,
        string="Manual Stage Override", copy=False)

    @api.depends('state', 'out_reason', 'estimate_status',
                 'job_card_status', 'invoice_status', 'payment_status',
                 'vehicle_status_override')
    def _compute_vehicle_status(self):
        overridden = self.filtered(
            lambda r: r.vehicle_status_override and r.state == 'in')
        for rec in overridden:
            rec.vehicle_status = rec.vehicle_status_override
        super(GatePassFormApi, self - overridden)._compute_vehicle_status()

    # ------------------------------------------------------------------
    # Custom form API
    # ------------------------------------------------------------------
    _FORM_FIELDS = [
        'name', 'state', 'date_in', 'date_out', 'promise_date', 'job_type',
        'out_reason', 'customer_type', 'partner_id', 'partner_phone',
        'partner_email', 'alternate_contact', 'whatsapp_number',
        'driver_name', 'driver_license_no', 'driver_license_expiry',
        'driver_mobile', 'vehicle_id', 'registration_no', 'vin', 'engine_no',
        'brand_id', 'model_id', 'vehicle_color_id', 'variant',
        'manufacturing_year', 'fuel_type', 'transmission', 'engine_capacity',
        'plate_source', 'odometer', 'customer_complaint', 'condition_remarks',
        'note', 'customer_note', 'booking_ref', 'advisor_id', 'vehicle_status',
        'estimate_status', 'job_card_status',
        'invoice_status', 'payment_status', 'send_whatsapp_notification',
        'send_sms_notification', 'booking_res_id',
        'job_card_count',
        'estimate_count', 'invoice_count', 'history_count',
    ]

    _WRITABLE_FIELDS = {
        'date_in', 'promise_date', 'job_type', 'out_reason', 'customer_type',
        'partner_id', 'alternate_contact', 'whatsapp_number', 'driver_name',
        'driver_license_no', 'driver_license_expiry', 'driver_mobile',
        'vehicle_id', 'registration_no', 'vin', 'engine_no', 'variant',
        'manufacturing_year', 'fuel_type', 'transmission', 'engine_capacity',
        'plate_source', 'odometer', 'customer_complaint', 'condition_remarks',
        'note', 'customer_note', 'booking_ref', 'advisor_id',
        'send_whatsapp_notification', 'send_sms_notification',
        'vehicle_status_override', 'booking_res_id',
    }

    @api.model
    def _form_selections(self):
        def sel(model, field):
            return [{'value': v, 'label': l} for v, l in
                    self.env[model]._fields[field]._description_selection(
                        self.env)]
        return {
            'state': sel('fleet.gate.pass', 'state'),
            'vehicle_status': sel('fleet.gate.pass', 'vehicle_status'),
            'job_type': sel('fleet.gate.pass', 'job_type'),
            'customer_type': sel('fleet.gate.pass', 'customer_type'),
            'fuel_type': sel('fleet.gate.pass', 'fuel_type'),
            'transmission': sel('fleet.gate.pass', 'transmission'),
            'out_reason': sel('fleet.gate.pass', 'out_reason'),
            'payment_status': sel('fleet.gate.pass', 'payment_status'),
            'estimate_status': sel('fleet.gate.pass', 'estimate_status'),
            'job_card_status': sel('fleet.gate.pass', 'job_card_status'),
            'invoice_status': sel('fleet.gate.pass', 'invoice_status'),
            'log_type': sel('fleet.gate.pass.log', 'log_type'),
            'timeline_event': sel('fleet.gate.pass.timeline', 'event'),
        }

    @api.model
    def form_load(self, gate_pass_id=False, domain=None):
        """Single RPC: full payload for the custom OWL form."""
        ids = self.search(domain or [], order='id desc', limit=1000).ids
        payload = {
            'ids': ids,
            'selections': self._form_selections(),
            'record': False, 'logs': [], 'timeline': [],
        }
        payload['booking_model'] = self._booking_model()
        if not gate_pass_id:
            return payload
        rec = self.browse(gate_pass_id)
        rec.check_access('read')
        data = rec.read(self._FORM_FIELDS)[0]
        for m2o in ('partner_id', 'vehicle_id', 'brand_id', 'model_id',
                    'vehicle_color_id', 'advisor_id'):
            data[m2o] = {'id': data[m2o][0], 'name': data[m2o][1]} \
                if data[m2o] else False
        payload['record'] = data
        payload['logs'] = rec.log_ids.read(
            ['log_type', 'date', 'user_id', 'advisor_id', 'remarks'])
        payload['timeline'] = rec.timeline_ids.read(
            ['event', 'date', 'user_id', 'note'])
        payload['booking'] = self._booking_info(rec._booking_record())
        payload['booking_model'] = self._booking_model()
        return payload

    @api.model
    def form_save(self, gate_pass_id, vals):
        vals = {k: v for k, v in vals.items() if k in self._WRITABLE_FIELDS}
        for k in ('driver_license_expiry',):
            if not vals.get(k):
                vals.pop(k, None)
        if gate_pass_id:
            rec = self.browse(gate_pass_id)
            rec.write(vals)
        else:
            rec = self.create(vals)
        return rec.id

    def action_open_custom_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'odex_gatepass_form',
            'name': self.name or _('Gate Pass'),
            'params': {'gate_pass_id': self.id},
        }
