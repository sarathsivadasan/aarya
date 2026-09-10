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

    technician_part_link_field = fields.Char(
        related='company_id.technician_part_link_field',
        readonly=False, string='Job Card / Inspection Link Field')


class ResCompany(models.Model):
    _inherit = 'res.company'

    technician_late_job_threshold = fields.Float(
        string='Late Job Threshold (Hours)', default=0.0,
        help='Extra hours of grace past the promise date before a job is '
             'flagged "Late" on the Performance page. 0 = flag as soon as '
             "today's date passes the promise date.")

    # v4.0.0: the Parts tab keeps the `part` value in step between a
    # Vehicle Inspection and the Job Card it became. Those are two
    # project.task rows joined by a many2one that lives in job_card /
    # vehicle_inspection_report, and the field name differs by install.
    # Leave this blank and the module probes for any project.task ->
    # project.task many2one at runtime; set it to pin the exact field and
    # skip the probe entirely.
    technician_part_link_field = fields.Char(
        string='Job Card / Inspection Link Field',
        help='Name of the many2one on project.task that links a Job Card '
             'to the Vehicle Inspection it came from (or vice versa), e.g. '
             '"inspection_id". Leave empty to detect it automatically.')
