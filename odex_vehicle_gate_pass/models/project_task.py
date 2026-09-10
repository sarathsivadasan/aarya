# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

class Task(models.Model):
    _inherit = "project.task"

    gate_pass_id = fields.Many2one('odex.gate.pass', string="Gatepass")

    @api.model_create_multi
    def create(self, vals_list):
        rec = super(Task, self).create(vals_list)
        if rec.is_vc == True:
            if rec.gate_pass_id and rec.gate_pass_id.state == 'vehicle':
                print("true,,,,,,,,,,,")
                rec.gate_pass_id.action_inspection()
        return rec

    def action_inspection_finished(self):
        self.gate_pass_id.update({'state': 'gatepass_out'})
        self.inspection_state = 'inspection_finished'
