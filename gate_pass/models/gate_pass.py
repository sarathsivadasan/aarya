# -*- coding: utf-8 -*-

import datetime
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

    # def _compute_inspection_count(self):
    #     Task = self.env['project.task']
    #     for rec in self:
    #         rec.inspection_count = Task.search_count([
    #             ('is_vc', '=', True),
    #             ('vehicle_id', '=', rec.vehicle_id.id),
    #             ('gate_pass_id', '=', rec.id),
    #         ]) if rec.vehicle_id else 0

    # def action_create_vehicle_inspection(self):
    #     self.ensure_one()

    #     if self.inspection_id:
    #         inspection = self.inspection_id
    #     else:
    #         inspection = self.env['project.task'].with_context(
    #             default_is_vc=True
    #         ).create({
    #             'is_vc': True,
    #             'partner_id': self.partner_id.id,
    #             'vehicle_id': self.vehicle_id.id,
    #             'gate_pass_id': self.id,
    #         })
    #         self.inspection_id = inspection.id

    #     action = self.env["ir.actions.actions"]._for_xml_id(
    #         "vehicle_inspection_report.action_vehicle_inspection"
    #     )

    #     action.update({
    #         "res_id": inspection.id,
    #         "view_mode": "form",
    #         "views": [
    #             (self.env.ref(
    #                 "vehicle_inspection_report.view_form_v_job_card_extension"
    #             ).id, "form")
    #         ],
    #     })

    #     return action

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


    @api.model
    def create(self, vals):
        name = self.env['ir.sequence'].next_by_code('gate.pass.seq')
        vals.update({
            'name': name
        })
        res = super(GatePass, self).create(vals)
        return res

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
            }