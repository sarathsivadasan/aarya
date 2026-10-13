# -*- coding: utf-8 -*-

import datetime
import re

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class GatePass(models.Model):
    _name = 'fleet.gate.pass'
    _description = "Fleet Gate Pass"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _order = 'id desc'


    name = fields.Char(
        string='Number',
        index=True,
        readonly=1,
    )
    state = fields.Selection([
        ('in', 'IN'),
        ('revisit', 'Revisit'),
        ('out', 'OUT')],
        default='in',
        tracking=True
    )
    partner_id = fields.Many2one('res.partner', string="Customer Name")
    partner_phone = fields.Char(string="Mobile No.", related="partner_id.phone", store=True)
    partner_email = fields.Char(string="Email ID", related="partner_id.email", store=True)
    alternate_contact = fields.Char(string="Alternative Contact")
    alternate_mobile = fields.Char(string="Mobile No.")
    vehicle_id = fields.Many2one('fleet.vehicle', string="Registration Number")
    brand_id = fields.Many2one('fleet.vehicle.model.brand', related="vehicle_id.vehicle_make_id", string="Brand")
    model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    vehicle_color_id = fields.Many2one('vehicle.color', string="Colors", related="vehicle_id.color_id")
    date_in = fields.Datetime('Date Time In', default=fields.Datetime.now)
    date_out = fields.Datetime('Date Time Out')
    approved_id = fields.Many2one('res.users', string="Approved By", default=lambda self: self.env.user)
    job_card_count = fields.Integer(
        string="Job Cards",
        compute="_compute_job_card_count"
    )
    # inspection_count = fields.Integer(
    #     string="Vehicle Inspection",
    #     compute="_compute_inspection_count"
    # )
    # inspection_id = fields.Many2one(
    #     'project.task',
    #     string="Vehicle Inspection",
    #     readonly=True,
    #     copy=False,
    # )
    note = fields.Html(string="Note")

    # ------------------------------------------------------------------
    # Booking integration (odex_workshop_booking)
    # ------------------------------------------------------------------
    booking_id = fields.Many2one(
        'odex.workshop.booking', string="Booking", readonly=True,
        copy=False, index=True, ondelete='set null', tracking=True)
    booking_date = fields.Date(
        string="Booking Date", related='booking_id.booking_date')
    booking_time = fields.Char(
        string="Booking Time", related='booking_id.time_label')
    service_type_id = fields.Many2one(
        'odex.booking.service.type', string="Service Type", copy=False)
    complaint = fields.Text(string="Vehicle Complaint")
    advisor_id = fields.Many2one(
        'res.users', string="Service Advisor", copy=False)
    vehicle_plate = fields.Char(
        string="Plate Number", related='vehicle_id.license_plate')
    vehicle_vin = fields.Char(
        string="VIN / Chassis", related='vehicle_id.vin_sn')
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)

    # def _compute_inspection_count(self):
    #     Task = self.env['project.task']
    #     for rec in self:
    #         rec.inspection_count = Task.search_count([
    #             ('is_vc', '=', True),
    #             ('vehicle_id', '=', rec.vehicle_id.id),
    #             ('gate_pass_id', '=', rec.id),
    #         ]) if rec.vehicle_id else 0

    def action_create_job_card(self):
        self.ensure_one()
        missing = [label for label, ok in (
            (_("Customer Name"), self.partner_id),
            (_("Contact Number"), self.cc_partner_phone or self.cc_partner_mobile),
            (_("Vehicle"), self.vehicle_id),
        ) if not ok]
        if missing:
            raise UserError(_("Fill these before creating a JobCard:\n- %s", "\n- ".join(missing)))
        return {
            "type": "ir.actions.act_window",
            "name": _("Job Card"),
            "res_model": "project.task",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {'default_partner_id': self.partner_id.id,
                        'default_cc_partner_phone': self.phone,
                        'default_vehicle_id': self.vehicle_id.id,
                        'default_odometer': self.booking_id.crm_id.odometer_reading,}
        }

    # def action_view_vehicle_inspection(self):
    #     self.ensure_one()

    #     inspections = self.env['project.task'].search([
    #         ('is_vc', '=', True),
    #         ('vehicle_id', '=', self.vehicle_id.id)
    #     ])

    #     action = self.env["ir.actions.actions"]._for_xml_id(
    #         "vehicle_inspection_report.action_vehicle_inspection"
    #     )

    #     action['domain'] = [('id', 'in', inspections.ids)]

    #     if len(inspections) == 1:
    #         action.update({
    #             'view_mode': 'form',
    #             'res_id': inspections.id,
    #         })

    #     return action


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('gate.pass.seq')
        return super().create(vals_list)

    @api.model
    def _prepare_vals_from_booking(self, booking):
        """Gate pass values copied from an ``odex.workshop.booking``."""
        vals = {
            'booking_id': booking.id,
            'partner_id': booking.partner_id.id,
            'vehicle_id': booking.vehicle_id.id,
            'service_type_id': booking.service_type_id.id,
            'complaint': booking.complaint,
            'advisor_id': booking.advisor_id.id,
            'company_id': booking.company_id.id or self.env.company.id,
            'date_in': fields.Datetime.now(),
            'state': 'in',
        }
        # A contact number given on the booking that differs from the one on
        # the customer record is kept as the alternate mobile.
        def digits(number):
            return re.sub(r'\D', '', number or '')
        mobile = booking.mobile or booking.phone
        known = {digits(booking.partner_id.phone), digits(booking.partner_id.mobile)}
        if mobile and digits(mobile) not in known:
            vals['alternate_mobile'] = mobile
        notes = []
        if booking.customer_note:
            notes.append(Markup('<p><b>%s:</b> %s</p>') % (
                _("Customer Notes"), booking.customer_note))
        if booking.note:
            notes.append(booking.note)
        if notes:
            vals['note'] = Markup('').join(notes)
        return vals

    def action_view_booking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Booking'),
            'res_model': 'odex.workshop.booking',
            'view_mode': 'form',
            'res_id': self.booking_id.id,
        }

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        for rec in self:
            if rec.vehicle_id and rec.vehicle_id.partner_id:
                rec.partner_id = rec.vehicle_id.partner_id.id

    def vehicle_out(self):
        for rec in self:
            rec.date_out = fields.Datetime.now()
            rec.state = 'out'

    def vehicle_revisit(self):
        for rec in self:
            rec.state = 'revisit'

    def _compute_job_card_count(self):
        Task = self.env['project.task']
        for rec in self:
            job_card_count = 0
            if rec.vehicle_id:
                 job_card_count = Task.search_count([
                     ('is_jobcard', '=', True),
                     ('vehicle_id', '=', rec.vehicle_id.id)
                ])
            rec.job_card_count = job_card_count

    def action_view_job_card(self):
        if self.vehicle_id:
            Task = self.env['project.task']
            job_card  = Task.search([
                ('is_jobcard', '=', True), ('vehicle_id', '=', self.vehicle_id.id)
            ])
            print("job_cardjob_cardjob_card",job_card)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Job Card'),
                'res_model': 'project.task',
                'view_mode': 'list,form',
                'domain': [
                    ('id', 'in', job_card.ids)],
                "context": {'default_partner_id': self.partner_id.id,
                        'default_cc_partner_phone': self.phone,
                        'default_vehicle_id': self.vehicle_id.id,
                        'default_odometer': self.booking_id.crm_id.odometer_reading,}
            }