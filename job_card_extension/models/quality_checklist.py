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
    condition = fields.Selection([
        ('g', "Good"),
        ('w', "Warning"),
        ('b', "Bad")], string="Condition",
        help="G / W / B result of the inspection item. Empty until the inspector picks one.")
    is_yes_no = fields.Boolean(
        string="Yes / No Item", compute="_compute_is_yes_no", store=True,
        help="Miscellaneous items are answered Yes / No instead of G / W / B.")

    @api.depends('checklist_name_id.name', 'name', 'display_type')
    def _compute_is_yes_no(self):
        for rec in self:
            if rec.display_type:
                rec.is_yes_no = False
                continue
            category = (rec.checklist_name_id.name or '').strip().lower()
            item = (rec.name or '').strip().lower()
            # Miscellaneous section items ("Checked ...") are answered with a simple toggle.
            rec.is_yes_no = category.startswith('miscel') or item.startswith('checked')


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