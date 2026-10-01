# -*- coding: utf-8 -*-
#
# v4.0.0 - the log is now the audit trail the administrator view reads.
# Every Start / Pause / Resume / Stop, whoever triggered it, records:
#   * job reference          -> task_id (+ job_reference, stored so the
#                               reference survives even if the task is
#                               renamed later)
#   * technician             -> technician_id (the employee the work
#                               belongs to - NOT necessarily the user who
#                               pressed the button)
#   * action performed       -> action
#   * date and time          -> log_date
#   * user who performed it  -> user_id
#   * whether it was an administrator override -> is_admin_action
# analytic_line_id ties the entry to the exact work record whose timer
# moved, so a job with several technicians stays unambiguous.

from odoo import api, fields, models


class TechnicianLog(models.Model):
    _name = 'technician.log'
    _description = 'Technician Action Log'
    _order = 'log_date desc, id desc'
    _rec_name = 'action'

    task_id = fields.Many2one('project.task', string='Job Card',
                              required=True, ondelete='cascade', index=True)
    analytic_line_id = fields.Many2one(
        'account.analytic.line', string='Work Record', ondelete='cascade',
        index=True,
        help='The exact technician work record whose timer this entry '
             'refers to. Empty for job-level events (photos, QC, notes).')
    technician_id = fields.Many2one(
        'hr.employee', string='Technician', index=True,
        help='The technician the work belongs to. For an administrator '
             'action this is still the technician, while User below is '
             'the administrator who performed it.')
    job_reference = fields.Char(
        string='Job Reference',
        help='Job Card number captured at the time of the action.')
    # v5.0.0: Vehicle Inspection support was removed and nothing writes
    # 'inspection' any more. The value is kept ONLY so log rows written
    # before the removal keep their origin instead of being blanked by
    # the upgrade (Odoo nulls removed selection values).
    record_type = fields.Selection([
        ('job_card', 'Job Card'),
        ('inspection', 'Vehicle Inspection (legacy)'),
        ('other', 'Other'),
    ], string='Origin', default='other')
    action = fields.Selection([
        ('started', 'Started'),
        ('paused', 'Paused'),
        ('resumed', 'Resumed'),
        ('completed', 'Completed'),
        ('photo_uploaded', 'Photo Uploaded'),
        ('qc_updated', 'QC Updated'),
        ('parts_requested', 'Parts Requested'),
        ('parts_updated', 'Parts Updated'),
        ('notes_added', 'Notes Added'),
        ('time_extension_requested', 'Time Extension Requested'),
        ('other', 'Other'),
    ], string='Action', required=True, default='other')
    description = fields.Char(string='Description')
    user_id = fields.Many2one('res.users', string='User',
                              default=lambda self: self.env.user, required=True)
    is_admin_action = fields.Boolean(
        string='Administrator Action',
        help='Ticked when the action was performed from the administrator '
             'view on behalf of the technician.')
    log_date = fields.Datetime(string='Date/Time', default=fields.Datetime.now, required=True)

    ACTION_LABEL_MAP = {
        'started inspection': 'started',
        'started': 'started',
        'paused': 'paused',
        'resumed': 'resumed',
        'completed': 'completed',
        'stopped': 'completed',
        'photo uploaded': 'photo_uploaded',
        'qc updated': 'qc_updated',
        'parts requested': 'parts_requested',
        'parts updated': 'parts_updated',
        'notes added': 'notes_added',
        'time extension requested': 'time_extension_requested',
    }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            raw = vals.get('action')
            if raw:
                vals['action'] = self.ACTION_LABEL_MAP.get(raw.strip().lower(), 'other')
            # backfill the denormalised reference / origin from the task
            if vals.get('task_id') and not vals.get('job_reference'):
                task = self.env['project.task'].sudo().browse(vals['task_id'])
                if task.exists():
                    vals['job_reference'] = (
                        task.number if task.is_jobcard and task.number else task.name) or ''
                    vals.setdefault(
                        'record_type', 'job_card' if task.is_jobcard else 'other')
        return super().create(vals_list)

    def to_portal_dict(self):
        self.ensure_one()
        return {
            'id': self.id,
            'date': self.log_date and self.log_date.isoformat(),
            'action': self.action,
            'action_label': dict(self._fields['action'].selection).get(
                self.action, self.action),
            'description': self.description or '',
            'user': self.user_id.display_name,
            'technician': self.technician_id.display_name or '',
            'job_reference': self.job_reference or (
                self.task_id.display_name if self.task_id else ''),
            'record_type': self.record_type,
            'is_admin_action': self.is_admin_action,
            'line_id': self.analytic_line_id.id,
            'task_id': self.task_id.id,
        }
