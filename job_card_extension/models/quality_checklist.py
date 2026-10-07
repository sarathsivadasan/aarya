from odoo import models, fields, api

INSPECTION_TYPES = [
    ('qc', 'QC'),
    ('pre', 'Pre Inspection'),
    ('final', 'Final Inspection'),
]


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
    # Existing rows get 'qc' when the column is added, so the QC tab is unchanged.
    inspection_type = fields.Selection(INSPECTION_TYPES, string="Inspection", default='qc',
                                       required=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Lines added from the Pre/Final tabs ("Add an item / section / note")
        # arrive with serial_no 0: append them after the existing points.
        next_serial = {}
        for vals in vals_list:
            itype = vals.get('inspection_type')
            task_id = vals.get('job_card_id')
            if itype in ('pre', 'final') and task_id and not vals.get('serial_no'):
                key = (task_id, itype)
                if key not in next_serial:
                    last = self.search([('job_card_id', '=', task_id), ('inspection_type', '=', itype)],
                                       order='serial_no desc', limit=1)
                    next_serial[key] = (last.serial_no or 0) + 1
                vals['serial_no'] = next_serial[key]
                next_serial[key] += 1
        return super().create(vals_list)
