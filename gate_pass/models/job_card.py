from datetime import date, datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class Task(models.Model):
    _inherit = "project.task"

    gate_pass_id = fields.Many2one('fleet.gate.pass',string="Gate Pass")

    @api.onchange('date_end')
    def onchange_gate_pass_id(self):
        for rec in self:
            if rec.gate_pass_id:
                rec.gate_pass_id.date_out = rec.date_end