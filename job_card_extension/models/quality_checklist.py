from odoo import models, fields, api

class QualityChecklist(models.Model):
    _inherit = "quality.checklist"

    job_card_id = fields.Many2one('project.task', string="Job Card")
    checklist_name_id = fields.Many2one(
        'quality.checklist.name',
        store=True,
        string="Checklists"
    )
    check_mark = fields.Boolean(string="Check Mark", default="True")
    serial_no = fields.Float(string="Serial No.")
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")


class InsQCChecklist(models.Model):
    _name = "ins.qc.checklist"
    _description = "Inspection Quality Checklist"

    job_card_id = fields.Many2one('project.task', string="Job Card")
    check_mark = fields.Boolean(string="Check Mark", default="True")
    serial_no = fields.Float(string="Serial No.")
    name = fields.Char(
        string = "Name",
        required=True,
        copy=False
    )
    description = fields.Text(string = "Remarks")


# class InsQCChecklistName(models.Model):
#     _name = "ins.qc.checklist.name"
#     _description = 'Inspection Quality Checklist Name'

#     name = fields.Char(
#         string = "Name"
#     )