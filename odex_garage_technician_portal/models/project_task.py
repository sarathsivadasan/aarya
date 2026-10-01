# -*- coding: utf-8 -*-
#
# v5.0.0 - Vehicle Inspection support removed. The portal now serves Job
# Cards only (is_jobcard); nothing here reads is_vc / inspection_state
# and the module no longer depends on vehicle_inspection_report.
#
# v2.0.0 - rebuilt against your actual installed schema after reviewing
# job_card, job_card_extension, garage_management_odoo and parts_request. Every field below is either genuinely new (no name
# collision anywhere in those five modules) or a deliberate read of a
# real, pre-existing field. Nothing here is guessed.
#
# FIELDS THIS MODULE DOES NOT OWN (read-only references, defined elsewhere):
#   is_jobcard, number                              -> job_card
#   vehicle_id, model_id, cylinder_count, odometer   -> garage_management_odoo
#   cc_stage_id, promise_date, job_type,
#   requested_services_ids, analytic_account_id      -> job_card_extension / job_card
#   allocated_hours, remaining_hours (via hr_timesheet on project.task)
#   user_ids (core project.task "Assignees")
#   job_card_daily_report_ids -> account.analytic.line, inverse of task_id (job_card)
#   quality_checklist_ids -> quality.checklist, inverse of job_card_id (job_card_extension)
#   part_requisition lines -> jobcard.part.requisition, inverse of job_id (parts_request)
#
# Source of truth for technician time is account.analytic.line
# (job_card_daily_report_ids), per your instruction. This module does NOT
# maintain its own start/end/pause timestamps on project.task anymore -
# earlier versions of this module did, and that was wrong: it assumed a
# single technician per task, which your schema explicitly supports
# multiple of (one account.analytic.line per technician per day).

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The 12 photo slots are real fields on project.task, owned by
# garage_management_odoo (image{N}, image{N}_name, image{N}_desc for
# N=1..12). image{N}_name is itself a Selection using this exact list
# (FLEET_IMAGES_NAME in garage_management_odoo/models/project_task.py);
# duplicated here only as a read-only lookup so the portal can label
# slots without importing that module's Python file directly.
PHOTO_SLOT_LABELS = {
    'front_view': 'Front view',
    'rear_view': 'Rear view',
    'left_side_view': 'Left side view',
    'right_side_view': 'Right side view',
    'top_view': 'Top view',
    'front_left_corner': 'Front-left corner',
    'front_right_corner': 'Front-right corner',
    'rear_left_corner': 'Rear-left corner',
    'rear_right_corner': 'Rear-right corner',
    'dent_scratch': 'Any visible dent, scratch, or damage',
    'odometer': 'Odometer reading',
}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # =====================================================================
    # NEW FIELDS (owned by this module - verified no collision)
    # =====================================================================
    technician_notes = fields.Html(string='Notes')

    # complaint_notes and technician_photo_ids removed (v3.0.0): they
    # duplicated data that already exists for real -
    # requested_services_ids (Complaints) and image1..image12
    # (Vehicle Photos), both on this same project.task record via
    # garage_management_odoo / job_card_extension. See PHOTO_SLOTS below
    # and the Complaints routes in controllers/main.py.

    technician_note_ids = fields.One2many(
        'technician.note', 'task_id', string='Timestamped Notes')
    technician_log_ids = fields.One2many(
        'technician.log', 'task_id', string='Technician Logs')

    # ---- aggregated from account.analytic.line (job_card_daily_report_ids) ----
    time_in = fields.Datetime(
        string='Time In', compute='_compute_task_time_summary', store=True,
        help='Earliest start_datetime across all technician timesheet lines.')
    time_out = fields.Datetime(
        string='Time Out', compute='_compute_task_time_summary', store=True,
        help='Latest end_datetime across all technician timesheet lines. '
             'Blank while any technician session is still open.')
    total_working_hours = fields.Float(
        string='Total Working Hours', compute='_compute_task_time_summary', store=True,
        help='Sum of total_hours across every technician timesheet line '
             '(job_card_daily_report_ids). Multiple technicians add up.')

    # ---- QC gate, derived from the REAL quality.checklist.check_mark ----
    qc_passed = fields.Boolean(
        string='QC Passed', compute='_compute_qc_passed', store=True,
        help='True once every quality.checklist line for this job (excluding '
             'section/note display rows) has check_mark = True.')

    # ---- job-level rollup of the per-technician timers ----
    # v4.0.0: report/job_report_templates.xml printed
    # `o.my_timer_status`, a field that was planned in v2 but never
    # actually declared anywhere - so the Print button in the technician
    # workspace raised as soon as it reached that line. This is the real
    # field it should have been: one status for the whole job, rolled up
    # from its technician work records.
    technician_job_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ], string='Job Status', compute='_compute_technician_job_status', store=True,
        help='Rolled up from the technician work records on this job: '
             'Running if anyone is actively working, Paused if work has '
             'started and everyone is paused, Completed once every record '
             'is closed.')

    # NOTE: the per-technician timer (status, start/pause/resume/end) now
    # lives on account.analytic.line, which is the portal's primary model.
    # project.task only provides task-level aggregates (time_in/time_out/
    # total_working_hours above) and the related data - complaints,
    # photos, parts, QC - fetched via task_id from a line.

    # =====================================================================
    # COMPUTE METHODS
    # =====================================================================
    @api.depends('job_card_daily_report_ids.start_datetime',
                 'job_card_daily_report_ids.end_datetime',
                 'job_card_daily_report_ids.total_hours')
    def _compute_task_time_summary(self):
        for task in self:
            lines = task.job_card_daily_report_ids
            starts = [d for d in lines.mapped('start_datetime') if d]
            task.time_in = min(starts) if starts else False

            if lines and all(line.end_datetime for line in lines):
                ends = [d for d in lines.mapped('end_datetime') if d]
                task.time_out = max(ends) if ends else False
            else:
                # at least one technician session is still open
                task.time_out = False

            task.total_working_hours = sum(lines.mapped('total_hours'))

    @api.depends('job_card_daily_report_ids.is_start_time',
                 'job_card_daily_report_ids.is_end_time',
                 'job_card_daily_report_ids.pause_datetime',
                 'job_card_daily_report_ids.resume_datetime')
    def _compute_technician_job_status(self):
        for task in self:
            lines = task.job_card_daily_report_ids
            if not lines:
                task.technician_job_status = 'not_started'
                continue
            statuses = [line.technician_status for line in lines]
            if 'running' in statuses:
                task.technician_job_status = 'running'
            elif all(s == 'completed' for s in statuses):
                task.technician_job_status = 'completed'
            elif 'paused' in statuses:
                task.technician_job_status = 'paused'
            else:
                task.technician_job_status = 'not_started'

    @api.depends('quality_checklist_ids.check_mark', 'quality_checklist_ids.display_type')
    def _compute_qc_passed(self):
        for task in self:
            lines = task.quality_checklist_ids.filtered(
                lambda l: not l.display_type)  # exclude section/note rows
            task.qc_passed = bool(lines) and all(lines.mapped('check_mark'))

    def action_request_more_time(self, extra_hours=0.5, reason=''):
        self.ensure_one()
        responsible = self.user_ids[:1].id if self.user_ids else self.env.user.id
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Time Extension Requested'),
            note=_('Extra %(hours)s hour(s) requested on %(task)s. Reason: %(reason)s') % {
                'hours': extra_hours, 'task': self.name, 'reason': reason or _('Not specified'),
            },
            user_id=responsible,
        )
        self._add_log('Time Extension Requested',
                       _('Requested +%.2f hour(s). Reason: %s') % (extra_hours, reason or '-'))
        return True

    def is_fully_completed(self):
        """True once every technician who has a timesheet line on this job
        has stopped it. False (not blocked) if nobody has started yet -
        that's 'not started', not 'complete'."""
        self.ensure_one()
        lines = self.job_card_daily_report_ids
        return bool(lines) and all(l.is_end_time for l in lines)

    def move_to_waiting_for_parts(self):
        """Best-effort: if a job.card.stage named 'Waiting for Parts'
        (or similar) exists, move this job there when a parts request is
        raised. Does nothing (silently) if cc_stage_id doesn't exist on
        this instance or no matching stage is found - we won't invent a
        stage record speculatively."""
        self.ensure_one()
        if 'cc_stage_id' not in self._fields:
            return
        Stage = self.env['job.card.stage'] if 'job.card.stage' in self.env else None
        if Stage is None:
            return
        stage = Stage.search([('name', 'ilike', 'waiting for part')], limit=1)
        if stage:
            self.cc_stage_id = stage.id

    def _add_log(self, action, description, line=None, technician=None,
                 is_admin=False):
        """Write one audit entry.

        line / technician / is_admin are optional so every existing caller
        (photos, QC, notes, parts) keeps working unchanged; the timer
        calls pass them so the administrator's activity log can show which
        work record moved, whose work it was, and whether an administrator
        performed it on the technician's behalf.
        """
        self.ensure_one()
        if technician is None and line is not None:
            technician = line.employees_id
        self.env['technician.log'].sudo().create({
            'task_id': self.id,
            'analytic_line_id': line.id if line else False,
            'technician_id': technician.id if technician else False,
            'job_reference': (self.number if self.is_jobcard and self.number
                              else self.name) or '',
            'record_type': 'job_card' if self.is_jobcard else 'other',
            'action': action,
            'description': description,
            'is_admin_action': bool(is_admin),
            'user_id': self.env.user.id,
        })

    # =====================================================================
    # ASSIGNMENT NOTIFICATIONS
    # Uses Odoo's standard chatter/inbox mechanism (message_post with
    # partner_ids) rather than a custom notification system - this shows
    # up in the assigned user's Discuss inbox/bell icon and is logged in
    # the task's own chatter, exactly like any other Odoo assignment.
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        for task in tasks:
            if task.is_jobcard and task.user_ids:
                task._notify_assignees(task.user_ids)
        return tasks

    def write(self, vals):
        old_assignees = {}
        if 'user_ids' in vals:
            for task in self.filtered(lambda t: t.is_jobcard):
                old_assignees[task.id] = task.user_ids
        res = super().write(vals)
        if 'user_ids' in vals:
            for task in self.filtered(lambda t: t.is_jobcard):
                newly_added = task.user_ids - old_assignees.get(task.id, self.env['res.users'])
                if newly_added:
                    task._notify_assignees(newly_added)
        return res

    def _notify_assignees(self, users):
        self.ensure_one()
        partners = users.mapped('partner_id')
        if not partners:
            return
        display_name = self.number if self.number else self.name
        self.message_post(
            body=_('You have been assigned to Job Card %(name)s.') % {
                'name': display_name,
            },
            partner_ids=partners.ids,
            subtype_xmlid='mail.mt_comment',
        )

    # =====================================================================
    # VEHICLE PHOTOS - reads/writes the real image{N}/image{N}_name/
    # image{N}_desc fields (garage_management_odoo) directly. No separate
    # photo model or storage - this task record IS the record shown on the
    # Job Card, so writes here are immediately the same data there.
    # =====================================================================
    def get_photo_slots(self):
        self.ensure_one()
        slots = []
        for n in range(1, 13):
            name_field = 'image%d_name' % n
            image_field = 'image%d' % n
            desc_field = 'image%d_desc' % n
            if name_field not in self._fields:
                continue
            name_key = self[name_field]
            slots.append({
                'slot': n,
                'name_key': name_key or False,
                'label': PHOTO_SLOT_LABELS.get(name_key, _('Additional photo %d') % n),
                'desc': self[desc_field] or '',
                'has_image': bool(self[image_field]),
            })
        return slots

    def set_photo_slot(self, slot, image=None, desc=None):
        self.ensure_one()
        image_field = 'image%d' % slot
        desc_field = 'image%d_desc' % slot
        name_field = 'image%d_name' % slot
        if image_field not in self._fields:
            raise UserError(_('Invalid photo slot.'))
        vals = {}
        if image is not None:
            vals[image_field] = image
        if desc is not None:
            vals[desc_field] = desc
        self.write(vals)
        label = PHOTO_SLOT_LABELS.get(self[name_field], _('Slot %d') % slot)
        self._add_log('Photo Uploaded', _('%s photo updated.') % label)

    def clear_photo_slot(self, slot):
        self.ensure_one()
        image_field = 'image%d' % slot
        if image_field not in self._fields:
            raise UserError(_('Invalid photo slot.'))
        self.write({image_field: False, '%s_desc' % image_field: False})
        self._add_log('Photo Uploaded', _('Slot %d photo removed.') % slot)

    # =====================================================================
    # CRON
    # =====================================================================
    @api.model
    def _cron_flag_overdue_jobs(self):
        """Log a supervisor-visible flag once per job whose promise_date
        has passed while at least one technician session is still open.
        Runs every 15 minutes (see data/ir_cron_data.xml)."""
        today = fields.Date.context_today(self)
        overdue = self.search([
            ('is_jobcard', '=', True),
            ('promise_date', '!=', False),
            ('promise_date', '<', today),
        ])
        for task in overdue:
            open_lines = task.job_card_daily_report_ids.filtered(lambda l: not l.is_end_time)
            if not open_lines:
                continue
            already_flagged = self.env['technician.log'].sudo().search_count([
                ('task_id', '=', task.id),
                ('action', '=', 'time_extension_requested'),
            ])
            if already_flagged:
                continue
            task.sudo()._add_log(
                'Time Extension Requested',
                _('Auto-flagged: past promise date (%s) with an open technician session.') % task.promise_date)

