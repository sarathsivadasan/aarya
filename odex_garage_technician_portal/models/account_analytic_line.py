# -*- coding: utf-8 -*-
#
# =====================================================================
# PRIMARY MODEL FOR THE TECHNICIAN PORTAL
# =====================================================================
# The portal starts here, not from project.task. A technician's work is
# a set of account.analytic.line rows (task.job_card_daily_report_ids).
# Each row is one unit of work on a Job Card (task_id.is_jobcard), and
# all related data (complaints, photos, parts, QC) is fetched through
# task_id from there.
#
# v5.0.0: Vehicle Inspection support removed - only Job Card lines are
# listed, and the inspection_state / inspection QC-gate side effects
# that used to run on Start / End are gone.
#
# ---------------------------------------------------------------------
# TWO PRE-EXISTING BUGS IN job_card_extension THAT WE WORK AROUND HERE
# (read-only; we do not modify that module)
# ---------------------------------------------------------------------
# 1. TIMESTAMP CONVENTION.
#    get_dubai_time() returns Dubai *wall-clock* time as a naive string
#    and assigns it to a Datetime field. Odoo stores Datetime fields as
#    UTC, so every stored timestamp is really Dubai local time wearing a
#    UTC label - i.e. +4h off true UTC.
#    Consequences:
#      * durations (end - start) are still CORRECT, because both ends
#        are shifted identically. total_hours is therefore trustworthy.
#      * absolute times are displayed +4h late by anything that assumes
#        UTC (including Odoo's own web client).
#      * a live "now - start" timer computed against real UTC would be
#        4h wrong (it would sit at 0.00 for the first four hours).
#    Rather than silently rewriting your historical data, we treat
#    SOURCE_TZ below as the convention the stored data is in, and do all
#    "now" comparisons and all display conversions relative to it. That
#    keeps every number correct without touching a single stored row.
#    THE REAL FIX is to make get_dubai_time() return fields.Datetime.now()
#    and migrate existing rows by -4h; ask and I'll write that migration.
#
# 2. STICKY PAUSE FLAG.
#    action_resume_time() sets is_resume_time=True but never clears
#    is_pause_time (the line that did is commented out in that module).
#    So is_pause_time stays True forever after the first pause. We derive
#    "paused right now" by comparing pause_datetime vs resume_datetime
#    instead, which stays correct over any number of cycles.
#
# ---------------------------------------------------------------------
# FIELD NAME NOTE
# ---------------------------------------------------------------------
# The brief said to filter by `employee_id`. On your schema that field
# exists (core hr_timesheet) but is NOT your technician - it defaults to
# whoever created the line. Your technician field is `employees_id`
# (plural), labelled "Technician", and it's the one every custom timer /
# onchange in job_card_extension uses. We filter on `employees_id`.
#
# ---------------------------------------------------------------------
# v4.0.0 - TIME TRACKING + ADMINISTRATOR CONTROL
# ---------------------------------------------------------------------
# * Start / Pause / Resume / End were refactored into shared _do_*()
#   internals. The technician entry points (action_technician_*) and the
#   new administrator entry points (action_admin_*) both go through them,
#   so an admin pause and a technician pause produce byte-identical time
#   tracking - only the permission check and the log entry differ.
# * Every write now also mirrors the timestamp onto the `start_time` /
#   `pause_time` / `resume_time` / `end_time` fields WHEN THEY EXIST on
#   your instance (see _time_vals). Nothing is declared for them here:
#   if they exist we fill them, if they don't the *_datetime fields
#   remain the single source of truth and nothing breaks.
# * total_pause_time accumulates across unlimited pause/resume cycles and
#   an open pause window is always closed out on End, so it is never
#   billed as work.
# * technician_net_hours = gross elapsed - total_pause_time, i.e. working
#   time EXCLUDING paused time.

from datetime import datetime

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# The timezone the stored datetimes are actually expressed in - see
# note 1 above. This mirrors get_dubai_time()'s hardcoded 'Asia/Dubai'.
SOURCE_TZ = 'Asia/Dubai'

# Groups allowed to drive ANOTHER technician's timer from the admin view.
ADMIN_GROUPS = (
    'odex_garage_technician_portal.group_garage_technician_supervisor',
    'base.group_system',
)

# Logical timestamp -> every field name that should carry it.
# The *_datetime names are the real job_card_extension fields and are
# always written. The bare *_time names are written ONLY if they exist on
# this instance (your brief names them; they are not declared here so we
# never shadow or redefine a field somebody else owns).
TIME_FIELD_ALIASES = {
    'start': ('start_datetime', 'start_time'),
    'pause': ('pause_datetime', 'pause_time'),
    'resume': ('resume_datetime', 'resume_time'),
    'end': ('end_datetime', 'end_time'),
}


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    technician_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ], string='Technician Status', compute='_compute_technician_status')

    # Audit trail for THIS work record specifically. The task-level
    # One2many (project.task.technician_log_ids) still shows everything
    # for the job; this one narrows it to the technician session whose
    # timer actually moved, which is what an administrator reviewing a
    # multi-technician job needs.
    technician_log_ids = fields.One2many(
        'technician.log', 'analytic_line_id', string='Activity Log',
        readonly=True)

    # Working time EXCLUDING accumulated pauses. Stored so it can be
    # grouped/summed in list views and reports. Recomputed whenever any
    # of the three inputs changes, which covers every timer transition.
    technician_net_hours = fields.Float(
        string='Net Working Hours', compute='_compute_technician_net_hours',
        store=True, readonly=True, digits=(16, 2),
        help='Gross elapsed time (end - start) minus the accumulated '
             'paused time. This is the billable working time.')

    # =====================================================================
    # TIME CONVENTION HELPERS
    # =====================================================================
    @api.model
    def _source_now(self):
        """'Now', expressed in the same convention the stored datetimes
        use (see note 1). Never compare stored values against
        fields.Datetime.now() directly - that's true UTC and would be
        4h out."""
        return datetime.now(pytz.timezone(SOURCE_TZ)).replace(tzinfo=None)

    def _display_dt(self, dt):
        """Render a stored datetime in the timezone configured on the
        related Employee record (hr.employee.tz), per the brief. Falls
        back to SOURCE_TZ when the employee has no tz set."""
        if not dt:
            return False
        self.ensure_one()
        source = pytz.timezone(SOURCE_TZ)
        target_name = (self.employees_id.tz or SOURCE_TZ)
        try:
            target = pytz.timezone(target_name)
        except pytz.UnknownTimeZoneError:
            target = source
        return source.localize(dt).astimezone(target).strftime('%d/%m/%Y %H:%M')

    # ---------------------------------------------------------------------
    # TIME FIELD MIRRORING
    # ---------------------------------------------------------------------
    def _writable_field(self, fname):
        """True if we can safely ORM-write this field: it exists, and it
        is not a compute/related field without an inverse (writing those
        raises)."""
        field = self._fields.get(fname)
        if not field:
            return False
        if field.compute and not field.inverse:
            return False
        if field.related and field.readonly:
            return False
        return True

    def _coerce_time_value(self, fname, dt):
        """Cast a datetime to whatever type the target field actually is,
        so we work whether start_time/pause_time/end_time are Datetime,
        Date, Float (hour of day) or Char on your instance."""
        ftype = self._fields[fname].type
        if ftype == 'datetime':
            return dt
        if ftype == 'date':
            return dt.date()
        if ftype == 'float':
            # Odoo's usual "float time" convention: hour of day.
            return dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        if ftype in ('char', 'text'):
            return fields.Datetime.to_string(dt)
        return None

    def _time_vals(self, role, dt):
        """Values dict writing `dt` to every alias of `role` that exists
        and is writable on this instance."""
        self.ensure_one()
        vals = {}
        for fname in TIME_FIELD_ALIASES[role]:
            if not self._writable_field(fname):
                continue
            value = self._coerce_time_value(fname, dt)
            if value is not None:
                vals[fname] = value
        return vals

    # =====================================================================
    # STATUS
    # =====================================================================
    def _is_paused(self):
        self.ensure_one()
        if not self.pause_datetime or self.is_end_time:
            return False
        return not self.resume_datetime or self.pause_datetime > self.resume_datetime

    def _compute_technician_status(self):
        for line in self:
            if line.is_end_time:
                line.technician_status = 'completed'
            elif line._is_paused():
                line.technician_status = 'paused'
            elif line.is_start_time:
                line.technician_status = 'running'
            else:
                line.technician_status = 'not_started'

    @api.depends('start_datetime', 'end_datetime', 'total_pause_time')
    def _compute_technician_net_hours(self):
        for line in self:
            if not line.start_datetime:
                line.technician_net_hours = 0.0
                continue
            end = line.end_datetime or line._source_now()
            gross = (end - line.start_datetime).total_seconds() / 3600.0
            line.technician_net_hours = max(gross - (line.total_pause_time or 0.0), 0.0)

    def _elapsed_seconds(self):
        """Net worked seconds so far: freezes while paused, stops at
        end_datetime once ended, ticks otherwise."""
        self.ensure_one()
        if not self.start_datetime:
            return 0.0
        if self.end_datetime:
            end = self.end_datetime
        elif self._is_paused():
            end = self.pause_datetime
        else:
            end = self._source_now()
        gross = (end - self.start_datetime).total_seconds()
        return max(gross - (self.total_pause_time or 0.0) * 3600.0, 0.0)

    # =====================================================================
    # PERMISSIONS
    # =====================================================================
    def _check_is_mine(self):
        self.ensure_one()
        employee = self.env.user.employee_id
        if not employee or self.employees_id.id != employee.id:
            raise UserError(_('This work record is not assigned to you.'))
        return employee

    @api.model
    def _is_technician_admin(self):
        """Administrator = Garage Technician Supervisor or Odoo system
        administrator. Both are pre-existing groups; no new group is
        introduced."""
        return any(self.env.user.has_group(g) for g in ADMIN_GROUPS)

    def _check_admin(self):
        if not self._is_technician_admin():
            raise UserError(_('Only an administrator can control another '
                              'technician\'s job.'))
        return True

    @api.model
    def _running_line_for(self, employee):
        """That employee's currently-running line anywhere (started, not
        paused, not ended). Enforces one active job at a time;
        paused/completed lines elsewhere do not block."""
        if not employee:
            return self.browse()
        candidates = self.sudo().search([
            ('employees_id', '=', employee.id),
            ('is_start_time', '=', True),
            ('is_end_time', '=', False),
        ])
        return candidates.filtered(lambda l: not l._is_paused())[:1]

    @api.model
    def _my_running_line(self):
        """Backwards-compatible wrapper: my own running line."""
        return self._running_line_for(self.env.user.employee_id)

    # =====================================================================
    # TIMER INTERNALS
    # Both the technician buttons and the administrator buttons funnel
    # through these, so the resulting time tracking is identical.
    # `actor` is only used to word the log entry.
    # =====================================================================
    def _do_start(self, actor='technician'):
        self.ensure_one()
        if self.is_end_time:
            raise UserError(_('This work record is already completed.'))
        if self.is_start_time:
            raise UserError(_('This work record has already been started.'))
        running = self._running_line_for(self.employees_id)
        if running:
            raise UserError(
                _('%(tech)s is currently working on %(job)s. That job must be '
                  'paused or completed first.') % {
                    'tech': self.employees_id.name or _('This technician'),
                    'job': running.task_id.display_name or _('another job'),
                })
        now = self._source_now()
        vals = self._time_vals('start', now)
        vals['is_start_time'] = True
        self.sudo().write(vals)
        self._log('Started',
                  _('%(who)s started work.') % {'who': self._actor_label(actor)},
                  is_admin=(actor == 'admin'))
        return True

    def _do_pause(self, actor='technician'):
        self.ensure_one()
        if not self.is_start_time or self.is_end_time:
            raise UserError(_('This work record is not running.'))
        if self._is_paused():
            raise UserError(_('This work record is already paused.'))
        now = self._source_now()
        vals = self._time_vals('pause', now)
        vals['is_pause_time'] = True
        self.sudo().write(vals)
        self._log('Paused',
                  _('%(who)s paused work.') % {'who': self._actor_label(actor)},
                  is_admin=(actor == 'admin'))
        return True

    def _do_resume(self, actor='technician'):
        self.ensure_one()
        if not self._is_paused():
            raise UserError(_('This work record is not paused.'))
        now = self._source_now()
        # duration of the pause window that is closing right now
        pause_hours = max((now - self.pause_datetime).total_seconds() / 3600.0, 0.0)
        vals = self._time_vals('resume', now)
        vals.update({
            'is_resume_time': True,
            'is_pause_time': False,  # job_card_extension forgets to clear this
            'total_pause_time': (self.total_pause_time or 0.0) + pause_hours,
        })
        self.sudo().write(vals)
        self._log('Resumed',
                  _('%(who)s resumed work after %(mins).0f minute(s) paused.') % {
                      'who': self._actor_label(actor), 'mins': pause_hours * 60.0},
                  is_admin=(actor == 'admin'))
        return True

    def _do_end(self, actor='technician'):
        self.ensure_one()
        if not self.is_start_time:
            raise UserError(_('This work record has not been started.'))
        if self.is_end_time:
            raise UserError(_('This work record is already completed.'))
        now = self._source_now()
        vals = self._time_vals('end', now)
        vals['is_end_time'] = True
        # Close out an open pause window so it is never billed as work.
        if self._is_paused():
            pause_hours = max((now - self.pause_datetime).total_seconds() / 3600.0, 0.0)
            vals['total_pause_time'] = (self.total_pause_time or 0.0) + pause_hours
            vals['is_pause_time'] = False
        self.sudo().write(vals)
        self._sync_total_hours()
        self._log('Completed',
                  _('%(who)s completed work. Net working time %(net).2f h '
                    '(paused %(paused).2f h).') % {
                      'who': self._actor_label(actor),
                      'net': self.technician_net_hours,
                      'paused': self.total_pause_time or 0.0},
                  is_admin=(actor == 'admin'))
        return True

    def _sync_total_hours(self):
        """If total_hours is a plain stored field on this instance (i.e.
        job_card_extension does NOT compute it), make sure it holds the
        working time EXCLUDING pauses. If it IS computed, we leave it
        alone - its own compute owns it - and technician_net_hours is the
        pause-excluded figure to read instead."""
        self.ensure_one()
        field = self._fields.get('total_hours')
        if not field or field.compute or field.related or not field.store:
            return
        self.sudo().write({'total_hours': round(self.technician_net_hours, 2)})

    def _actor_label(self, actor):
        self.ensure_one()
        tech = self.employees_id.name or _('Technician')
        if actor == 'admin':
            return _('%(admin)s (administrator, on behalf of %(tech)s)') % {
                'admin': self.env.user.name, 'tech': tech}
        return tech

    # =====================================================================
    # TIMER - TECHNICIAN ENTRY POINTS (unchanged public API)
    # =====================================================================
    def action_technician_start(self):
        self.ensure_one()
        self._check_is_mine()
        return self._do_start(actor='technician')

    def action_technician_pause(self):
        self.ensure_one()
        self._check_is_mine()
        return self._do_pause(actor='technician')

    def action_technician_resume(self):
        self.ensure_one()
        self._check_is_mine()
        return self._do_resume(actor='technician')

    def action_technician_end(self):
        self.ensure_one()
        self._check_is_mine()
        return self._do_end(actor='technician')

    # =====================================================================
    # TIMER - ADMINISTRATOR ENTRY POINTS
    # Same time tracking, different permission check and log wording.
    # The log records that it was an administrator action.
    # =====================================================================
    def action_admin_start(self):
        self.ensure_one()
        self._check_admin()
        return self._do_start(actor='admin')

    def action_admin_pause(self):
        self.ensure_one()
        self._check_admin()
        return self._do_pause(actor='admin')

    def action_admin_resume(self):
        self.ensure_one()
        self._check_admin()
        return self._do_resume(actor='admin')

    def action_admin_end(self):
        self.ensure_one()
        self._check_admin()
        return self._do_end(actor='admin')

    def action_request_more_time(self, extra_hours=0.5, reason=''):
        self.ensure_one()
        self.task_id.action_request_more_time(extra_hours, reason)
        return True

    def _log(self, action, description, is_admin=False):
        self.ensure_one()
        if self.task_id:
            self.task_id._add_log(action, description, line=self,
                                  technician=self.employees_id,
                                  is_admin=is_admin)

    # =====================================================================
    # PORTAL QUERIES - everything the portal shows starts from here
    # =====================================================================
    @api.model
    def _my_lines_domain(self, task_type=None):
        employee = self.env.user.employee_id
        domain = [('employees_id', '=', employee.id if employee else False)]
        return domain + self._task_type_domain(task_type)

    @api.model
    def _task_type_domain(self, task_type=None):
        """The portal serves Job Cards only. task_type is still accepted
        so older callers keep working, but it no longer changes the
        result."""
        return [('task_id.is_jobcard', '=', True)]

    @api.model
    def _all_lines_domain(self, task_type=None):
        """Every assigned Job Card line in the workshop, whoever it
        belongs to. Used by the administrator view only."""
        return [('employees_id', '!=', False)] + self._task_type_domain(task_type)

    @api.model
    def get_technician_dashboard_counters(self):
        employee = self.env.user.employee_id
        if not employee:
            return {'assigned': 0, 'in_progress': 0, 'paused': 0,
                    'completed_today': 0, 'hours_today': 0.0}
        lines = self.search(self._my_lines_domain())
        today = self._source_now().date()
        counters = {'assigned': 0, 'in_progress': 0, 'paused': 0,
                    'completed_today': 0, 'hours_today': 0.0}
        for line in lines:
            status = line.technician_status
            if status == 'not_started':
                counters['assigned'] += 1
            elif status == 'running':
                counters['in_progress'] += 1
                if line.start_datetime and line.start_datetime.date() == today:
                    counters['hours_today'] += line._elapsed_seconds() / 3600.0
            elif status == 'paused':
                counters['paused'] += 1
                if line.start_datetime and line.start_datetime.date() == today:
                    counters['hours_today'] += line._elapsed_seconds() / 3600.0
            elif status == 'completed':
                if line.end_datetime and line.end_datetime.date() == today:
                    counters['completed_today'] += 1
                    counters['hours_today'] += line.total_hours
        counters['hours_today'] = round(counters['hours_today'], 2)
        return counters

    @api.model
    def get_admin_dashboard_counters(self):
        """Workshop-wide counters for the administrator view."""
        lines = self.sudo().search(self._all_lines_domain())
        today = self._source_now().date()
        counters = {'assigned': 0, 'in_progress': 0, 'paused': 0,
                    'completed_today': 0, 'technicians_active': 0}
        active_employees = set()
        for line in lines:
            status = line.technician_status
            if status == 'not_started':
                counters['assigned'] += 1
            elif status == 'running':
                counters['in_progress'] += 1
                active_employees.add(line.employees_id.id)
            elif status == 'paused':
                counters['paused'] += 1
            elif status == 'completed' and line.end_datetime \
                    and line.end_datetime.date() == today:
                counters['completed_today'] += 1
        counters['technicians_active'] = len(active_employees)
        return counters

    # =====================================================================
    # SERIALIZERS
    # =====================================================================
    def _task_label(self):
        self.ensure_one()
        task = self.task_id
        return (task.number if task.is_jobcard and task.number else task.name) or ''

    def to_portal_list_item(self):
        self.ensure_one()
        task = self.task_id
        return {
            'id': self.id,
            'task_id': task.id,
            'task_name': self._task_label(),
            'service': self.product_id.display_name if self.product_id else (self.name or ''),
            'vehicle': task.vehicle_id.display_name if task.vehicle_id else '',
            'customer': task.partner_id.display_name if task.partner_id else '',
            'priority_label': dict(task._fields['priority'].selection or {}).get(
                task.priority, task.priority),
            'record_type': 'job_card' if task.is_jobcard else 'other',
            'status': self.technician_status,
        }

    def to_admin_list_item(self):
        """One row of the administrator's "all assigned jobs" table."""
        self.ensure_one()
        task = self.task_id
        return {
            'id': self.id,
            'task_id': task.id,
            'task_name': self._task_label(),
            'record_type': 'job_card' if task.is_jobcard else 'other',
            'technician': self.employees_id.display_name or '',
            'technician_id': self.employees_id.id,
            'service': self.product_id.display_name if self.product_id else (self.name or ''),
            'vehicle': task.vehicle_id.display_name if task.vehicle_id else '',
            'customer': task.partner_id.display_name if task.partner_id else '',
            'status': self.technician_status,
            'start_display': self._display_dt(self.start_datetime),
            'pause_display': self._display_dt(self.pause_datetime),
            'resume_display': self._display_dt(self.resume_datetime),
            'end_display': self._display_dt(self.end_datetime),
            'total_pause_hours': round(self.total_pause_time or 0.0, 2),
            'net_hours': round(self.technician_net_hours or 0.0, 2),
            'total_hours': round(self.total_hours or 0.0, 2),
            'elapsed_seconds': round(self._elapsed_seconds()),
            'is_ticking': self.technician_status == 'running',
        }

    def to_portal_detail(self):
        self.ensure_one()
        task = self.task_id
        vehicle = task.vehicle_id

        vehicle_data = {}
        if vehicle:
            vehicle_data = {
                'name': vehicle.display_name,
                'model': vehicle.model_id.display_name if vehicle.model_id else '',
                'year': vehicle.model_year or '',
                'license_plate': vehicle.license_plate or '',
                'vin': vehicle.vin_sn or '',
                'cylinder_count': vehicle.cylinder_count if 'cylinder_count' in vehicle._fields else '',
                'image_url': '/web/image/fleet.vehicle/%s/image_128' % vehicle.id,
            }

        allocated = sum(task.requested_services_ids.mapped('assign_hours')) \
            if 'requested_services_ids' in task._fields else 0.0

        # every technician working this same task (via its analytic lines)
        siblings = task.job_card_daily_report_ids
        return {
            'id': self.id,
            'task_id': task.id,
            'task_name': self._task_label(),
            'record_type': 'job_card' if task.is_jobcard else 'other',
            'is_jobcard': task.is_jobcard,
            'service': self.product_id.display_name if self.product_id else (self.name or ''),
            'status': self.technician_status,
            'vehicle': vehicle_data,
            'customer': task.partner_id.display_name if task.partner_id else '',
            'job_type': task.job_type if 'job_type' in task._fields else False,
            'cc_stage': task.cc_stage_id.name if 'cc_stage_id' in task._fields and task.cc_stage_id else '',
            'priority_label': dict(task._fields['priority'].selection or {}).get(
                task.priority, task.priority),
            'promise_date': task.promise_date.strftime('%d/%m/%Y') if 'promise_date' in task._fields and task.promise_date else False,
            'allocated_hours': allocated,
            'qc_passed': task.qc_passed,
            # --- bay (backend-owned; portal is a UI layer only) ---
            'bay_supported': 'bay_id' in task._fields,
            'bay_id': task.bay_id.id if 'bay_id' in task._fields and task.bay_id else False,
            'bay_name': task.bay_id.display_name if 'bay_id' in task._fields and task.bay_id else '',
            'technician_notes': task.technician_notes or '',
            # --- time, all rendered in the employee's own timezone ---
            'start_display': self._display_dt(self.start_datetime),
            'pause_display': self._display_dt(self.pause_datetime),
            'resume_display': self._display_dt(self.resume_datetime),
            'end_display': self._display_dt(self.end_datetime),
            'total_pause_hours': round(self.total_pause_time or 0.0, 2),
            'net_hours': round(self.technician_net_hours or 0.0, 2),
            'total_hours': round(self.total_hours or 0.0, 2),
            # elapsed is computed server-side against the same convention
            # the data is stored in, so the browser never has to guess.
            'elapsed_seconds': round(self._elapsed_seconds()),
            'is_ticking': self.technician_status == 'running',
            'timezone': self.employees_id.tz or SOURCE_TZ,
            'technicians': [{
                'employee': l.employees_id.display_name if l.employees_id else _('(unassigned)'),
                'service': l.product_id.display_name if l.product_id else (l.name or ''),
                'start_display': l._display_dt(l.start_datetime),
                'end_display': l._display_dt(l.end_datetime),
                'total_pause_hours': round(l.total_pause_time or 0.0, 2),
                'total_hours': round(l.total_hours or 0.0, 2),
                'status': l.technician_status,
                'is_me': l.id == self.id,
            } for l in siblings],
        }

    # =====================================================================
    # ASSIGNMENT NOTIFICATION
    # A technician is assigned by setting employees_id on a line - not via
    # project.task.user_ids, which job_card_extension labels "Service
    # Advisor". So the notification fires from here.
    # =====================================================================
    def _notify_technician_assigned(self):
        for line in self:
            task, employee = line.task_id, line.employees_id
            if not task or not employee or not employee.user_id:
                continue
            if not task.is_jobcard:
                continue
            if employee.user_id.id == self.env.uid:
                continue  # don't notify someone about their own action
            display_name = task.number if task.number else task.name
            task.message_notify(
                partner_ids=employee.user_id.partner_id.ids,
                body=_('You have been assigned to Job Card %(name)s.') % {
                    'name': display_name,
                },
                subject=_('New Job Card assigned'),
                record_name=display_name,
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered(lambda l: l.employees_id)._notify_technician_assigned()
        return lines

    def write(self, vals):
        if 'employees_id' not in vals:
            return super().write(vals)
        before = {line.id: line.employees_id.id for line in self}
        res = super().write(vals)
        self.filtered(
            lambda l: l.employees_id and l.employees_id.id != before.get(l.id)
        )._notify_technician_assigned()
        return res
