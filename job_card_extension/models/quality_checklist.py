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
    """Pre Inspection / Final Inspection lines of the Job Card (ON / OFF + Remark)."""
    _name = "ins.qc.checklist"
    _description = "Inspection Quality Checklist"
    _order = "serial_no, id"

    job_card_id = fields.Many2one('project.task', string="Job Card")
    inspection_type = fields.Selection([
        ('pre', "Pre Inspection"),
        ('final', "Final Inspection")], string="Inspection", default='pre', index=True,
        help="Tab of the Job Card this line belongs to.")
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    check_mark = fields.Boolean(string="Check Mark", default="True")
    serial_no = fields.Float(string="Serial No.")
    name = fields.Char(
        string = "Name",
        required=True,
        copy=False
    )
    description = fields.Text(string = "Remarks")

    @api.model_create_multi
    def create(self, vals_list):
        """Lines added by hand (Add an item / section / note) get the next serial number of
        their tab, so they stay where they were added once the job card is saved."""
        default_type = self.env.context.get('default_inspection_type') or 'pre'
        last_serial = {}
        db_checked = set()
        for vals in vals_list:
            if vals.get('job_card_id') and vals.get('serial_no'):
                key = (vals['job_card_id'], vals.get('inspection_type') or default_type)
                last_serial[key] = max(last_serial.get(key, 0.0), vals['serial_no'])
        for vals in vals_list:
            if not vals.get('job_card_id') or vals.get('serial_no'):
                continue
            key = (vals['job_card_id'], vals.get('inspection_type') or default_type)
            if key not in db_checked:
                db_checked.add(key)
                last = self.search([('job_card_id', '=', key[0]), ('inspection_type', '=', key[1])],
                                   order='serial_no desc', limit=1)
                last_serial[key] = max(last_serial.get(key, 0.0), last.serial_no or 0.0)
            last_serial[key] = int(last_serial[key]) + 1
            vals['serial_no'] = last_serial[key]
        return super().create(vals_list)


# class InsQCChecklistName(models.Model):
#     _name = "ins.qc.checklist.name"
#     _description = 'Inspection Quality Checklist Name'

#     name = fields.Char(
#         string = "Name"
#     )