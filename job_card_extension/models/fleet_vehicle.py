from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    count_job_ids = fields.Integer(string="Count Jobs", compute="_count_job_ids")
    job_ids = fields.One2many("project.task", "vehicle_id", string="Job IDS", domain=[('is_jobcard', '=', True)])
    move_ids = fields.One2many("account.move", "vehicle_id", string="Invoices", domain=[('move_type', 'in', ['out_invoice', 'out_refund'])])
    count_move_ids = fields.Integer(string="Count Jobs", compute="_count_move_ids")

    @api.depends('job_ids')
    def _count_job_ids(self):
        for rec in self:
            rec.count_job_ids = len(rec.job_ids)

    def action_jobs_list(self):
        return {
            'name': ('Jobs'),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'context': {},
            'domain': [('id', 'in', self.job_ids.ids)],
            'target': 'current',
            'type': 'ir.actions.act_window',
        }


    @api.depends('move_ids')
    def _count_move_ids(self):
        for rec in self:
            rec.count_move_ids = len(rec.move_ids)

    def action_invoices_list(self):
        return {
            'name': ('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'context': {'default_move_type': 'out_invoice'},
            'domain': [('id', 'in', self.move_ids.ids)],
            'target': 'current',
            'type': 'ir.actions.act_window'
        }
