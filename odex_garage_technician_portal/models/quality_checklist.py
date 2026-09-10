# -*- coding: utf-8 -*-
# quality.checklist already exists (job_card base: name, description;
# job_card_extension: job_card_id, checklist_name_id, check_mark,
# serial_no, display_type). check_mark is the REAL pass/fail flag - the
# 'result' Selection an earlier version of this module invented has been
# removed. The real 'description' field (job_card base) is used for the
# QC tab's text column - an earlier version of this module added a
# redundant 'remarks' field here, which has been removed in favour of
# 'description' to match what Vehicle Inspection / Job Card actually
# show. image/checked_by/checked_date below are genuinely new additions
# (no collision, purely additive).

from odoo import api, fields, models, _


class QualityChecklist(models.Model):
    _inherit = 'quality.checklist'

    image = fields.Image(string='Photo', max_width=1024, max_height=1024)
    checked_by = fields.Many2one('hr.employee', string='Checked By')
    checked_date = fields.Datetime(string='Checked On')

    def write(self, vals):
        if 'check_mark' in vals:
            vals.setdefault('checked_date', fields.Datetime.now())
            employee = self.env.user.employee_id
            if employee:
                vals.setdefault('checked_by', employee.id)
        res = super().write(vals)
        if 'check_mark' in vals:
            for rec in self:
                if rec.job_card_id:
                    rec.job_card_id._add_log(
                        'QC Updated',
                        _('QC item "%s" marked %s.') % (
                            rec.checklist_name_id.display_name if rec.checklist_name_id else rec.name,
                            _('Pass') if rec.check_mark else _('Fail')))
        return res
