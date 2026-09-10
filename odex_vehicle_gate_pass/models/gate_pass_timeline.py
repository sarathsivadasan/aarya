# -*- coding: utf-8 -*-
from odoo import api, fields, models

STEPS = [
    ("gatepass_in", "Gatepass In"),
    ("vehicle", "Vehicle"),
    ("inspection", "Inspection"),
    ("rfq", "RFQ"),
    ("purchase", "Purchase"),
    ("quotation", "Quotation"),    
    ("jobcard", "Jobcard"),
    ("invoice", "Invoice"),
    ("gatepass_out", "Gatepass Out"),
]


class OdexGatePassTimeline(models.Model):
    _name = "odex.gate.pass.timeline"
    _description = "Gate Pass Timeline Step"
    _order = "sequence, id"

    gate_pass_id = fields.Many2one(
        "odex.gate.pass", string="Gate Pass", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    step = fields.Selection(STEPS, string="Step", required=True)
    status = fields.Selection(
        [("pending", "Pending"), ("done", "Done")], string="Status", default="pending"
    )
    date = fields.Datetime(string="Date")
    user_id = fields.Many2one("res.users", string="User")
    ref_model = fields.Char(string="Reference Model")
    ref_id = fields.Many2oneReference(
        string="Reference", model_field="ref_model"
    )
    note = fields.Char(string="Note")
    date_label = fields.Char(compute="_compute_date_label")

    @api.depends("date", "status")
    def _compute_date_label(self):
        for record in self:
            if record.status == "done" and record.date:
                localized = fields.Datetime.context_timestamp(record, record.date)
                record.date_label = localized.strftime("%d-%b-%Y %I:%M %p")
            else:
                record.date_label = "Pending"

    @api.depends("step")
    def _compute_display_name(self):
        labels = dict(STEPS)
        for record in self:
            record.display_name = labels.get(record.step, record.step or "")
