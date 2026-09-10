# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OdexGatePassInspection(models.Model):
    _name = "odex.gate.pass.inspection"
    _description = "Gate Pass Inspection Item"
    _order = "sequence, id"

    gate_pass_id = fields.Many2one(
        "odex.gate.pass", string="Gate Pass", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Check", required=True)
    result = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor"),
         ("na", "Not Applicable"), ("not_checked", "Not Checked")],
        string="Result",
        default="not_checked",
    )
    remark = fields.Char(string="Remark")

    @api.depends("name", "result")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or ""
