# -*- coding: utf-8 -*-
# v2.0.0: dropped "Default Estimated Hours" - it seeded a per-task
# estimated_hours field that no longer exists (project.task already has
# allocated_hours via hr_timesheet). Kept + actually wired up
# late_job_threshold, which the v1 controller defined but never read.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    technician_late_job_threshold = fields.Float(
        related='company_id.technician_late_job_threshold',
        readonly=False, string='Late Job Threshold (Hours)')


class ResCompany(models.Model):
    _inherit = 'res.company'

    technician_late_job_threshold = fields.Float(
        string='Late Job Threshold (Hours)', default=0.0,
        help='Extra hours of grace past the promise date before a job is '
             'flagged "Late" on the Performance page. 0 = flag as soon as '
             "today's date passes the promise date.")

    # v5.0.0: technician_part_link_field (Job Card <-> Vehicle Inspection
    # link for the Parts tab) removed together with Vehicle Inspection
    # support.
