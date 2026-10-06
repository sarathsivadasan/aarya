# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Task(models.Model):
    _inherit = "project.task"

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', string="Gate Pass", index=True)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        for task in tasks.filtered('gate_pass_id'):
            if task.is_jobcard:
                task.gate_pass_id._log_timeline('job_card')
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            for task in self.filtered(
                    lambda t: t.gate_pass_id and t.state == '1_done'):
                gp = task.gate_pass_id
                if task.is_jobcard and gp.job_card_status == 'completed':
                    gp._log_timeline('ready')
        return res
