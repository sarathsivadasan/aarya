# -*- coding: utf-8 -*-
# job_card already adds `workshop_position_type` (Selection: leader/worker)
# to hr.employee.base / hr.employee - that IS the real "is this person a
# garage technician" signal. An earlier version of this module invented a
# separate is_garage_technician Boolean; removed in favour of the real
# field. technician_skills / technician_experience_years below are
# genuinely new (no equivalent found anywhere in the reviewed modules).

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    technician_skills = fields.Char(
        string='Skills',
        help='Comma separated list, e.g. "Engine Diagnostics, AC Repair, Electrical".')
    technician_experience_years = fields.Float(string='Experience (Years)')

    technician_work_status = fields.Selection([
        ('working', 'Working'),
        ('paused', 'Paused'),
        ('idle', 'Idle'),
    ], string='Technician Status', compute='_compute_technician_work_status')

    technician_current_vehicle = fields.Char(
        string='Current Vehicle', compute='_compute_technician_work_status',
        help='Model + license plate of the vehicle this employee is '
             'currently working on (running or paused job). Falls back to '
             'the most recently assigned vehicle when nothing is started.')

    def is_workshop_technician(self):
        """Who counts as a garage technician for portal purposes.

        workshop_position_type (job_card) is the intended signal, but on
        your instance it isn't set on every technician - which is why the
        status label rendered for nobody. So we also accept: the linked
        user is in the Garage Technician group, OR the employee already
        has timesheet lines on a job card.
        """
        self.ensure_one()
        if self.workshop_position_type:
            return True
        if self.user_id and self.user_id.has_group(
                'odex_garage_technician_portal.group_garage_technician'):
            return True
        return bool(self.env['account.analytic.line'].search_count([
            ('employees_id', '=', self.id),
            ('task_id.is_jobcard', '=', True),
        ]))

    def _compute_technician_work_status(self):
        """Derived live from the SAME account.analytic.line rows the
        portal timer uses (job_card_daily_report_ids on project.task) -
        no separate tracking, just a different lens on existing data.

        Applies to EVERY employee, all departments and job positions
        (per request - no technician gate):
        working -> at least one job started and actively running
        paused  -> has open sessions, but all of them are paused ("Idle")
        idle    -> no open session at all ("Not working")

        Pause detection compares timestamps rather than is_pause_time,
        because job_card_extension's action_resume_time() never clears
        that flag (see the note in project_task.py).
        """
        AAL = self.env['account.analytic.line']
        for employee in self:
            open_lines = AAL.search([
                ('employees_id', '=', employee.id),
                ('is_start_time', '=', True),
                ('is_end_time', '=', False),
            ], order='id desc')
            if not open_lines:
                employee.technician_work_status = 'idle'
                # nothing started - fall back to the newest ASSIGNED line
                assigned = AAL.search([
                    ('employees_id', '=', employee.id),
                    ('is_start_time', '=', False),
                    ('is_end_time', '=', False),
                    ('task_id', '!=', False),
                ], order='id desc', limit=1)
                employee.technician_current_vehicle = self._vehicle_label(assigned)
                continue
            running = open_lines.filtered(lambda l: not l._is_paused())
            employee.technician_work_status = 'working' if running else 'paused'
            # show the vehicle of the ACTIVE job (running first, else the
            # most recently paused one)
            employee.technician_current_vehicle = self._vehicle_label(
                running[:1] or open_lines[:1])

    @api.model
    def _vehicle_label(self, line):
        """'Model - Plate' for the vehicle on a work record's task, or False."""
        vehicle = line.task_id.vehicle_id if line and line.task_id else False
        if not vehicle:
            return False
        parts = []
        if vehicle.model_id:
            parts.append(vehicle.model_id.name)
        if vehicle.license_plate:
            parts.append(vehicle.license_plate)
        return ' - '.join(parts) or vehicle.display_name
