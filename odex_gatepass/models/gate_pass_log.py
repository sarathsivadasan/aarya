# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GatePassLog(models.Model):
    _name = 'fleet.gate.pass.log'
    _description = "Gate Pass Entry / Exit Log"
    _order = 'date desc, id desc'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', required=True, ondelete='restrict', index=True)
    log_type = fields.Selection([
        ('in', 'IN'),
        ('out', 'OUT'),
        ('revisit', 'Revisit'),
        ('rework', 'Rework'),
        ('continuation', 'Continuation')],
        string="Type", required=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string="User", required=True)
    advisor_id = fields.Many2one('res.users', string="Advisor")
    remarks = fields.Char()

    def write(self, vals):
        allowed = {'remarks'}
        if set(vals) - allowed:
            raise UserError(_("Entry/Exit logs cannot be modified."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Entry/Exit logs can never be deleted."))


class GatePassTimeline(models.Model):
    _name = 'fleet.gate.pass.timeline'
    _description = "Gate Pass Timeline"
    _order = 'date asc, id asc'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', required=True, ondelete='cascade', index=True)
    event = fields.Selection([
        ('gate_pass_in', 'Gate Pass IN'),
        ('inspection', 'Inspection'),
        ('estimate', 'Estimate'),
        ('approval', 'Approval'),
        ('job_card', 'Job Card'),
        ('invoice', 'Sales Invoice'),
        ('payment', 'Payment'),
        ('ready', 'Ready for Delivery'),
        ('gate_pass_out', 'Gate Pass OUT'),
        ('revisit', 'Revisit'),
        ('completed', 'Completed')],
        required=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string="By", required=True)
    note = fields.Char()
