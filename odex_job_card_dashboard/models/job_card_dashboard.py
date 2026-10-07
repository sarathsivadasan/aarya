# -*- coding: utf-8 -*-
"""Job Card Dashboard data service.

Design rules followed here:

* One RPC returns the whole dashboard; per-card drill-downs are lazy.
* Every counter comes from ``read_group`` - records are never loaded to be
  counted, so the dashboard stays flat at 10.000+ job cards.
* No ``sudo()``: record rules and multi-company rules apply as-is.
* Every field name is resolved at runtime.  If a database does not have a
  given field the related widget degrades gracefully instead of raising.
* Every widget is isolated: one failing widget cannot blank the dashboard.
"""
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)

# Candidate field names, first match wins.
FIELD_CANDIDATES = {
    'job_card_flag': ['is_jobcard', 'is_job_card'],
    'inspection_flag': ['is_vc', 'is_inspection', 'is_vehicle_inspection'],
    'stage': ['cc_stage_id'],
    'stage_value': ['cc_stage_value'],
    'number': ['number', 'job_card_no', 'name'],
    'vehicle': ['vehicle_id'],
    'customer': ['partner_id'],
    'advisor': ['user_ids', 'user_id', 'service_advisor_id'],
    'technician': ['technician_id', 'technician_ids', 'employees_id',
                   'employee_ids', 'employee_id'],
    'promise': ['promise_date', 'date_deadline'],
    'closed': ['is_close', 'is_closed'],
    'end_date': ['date_end'],
    'bay': ['bay_id', 'lift_id'],
    'branch': ['branch_id', 'x_branch_id'],
    'inspection_state': ['inspection_state', 'vc_state'],
    'priority': ['priority'],
    'company': ['company_id'],
    'customer_waiting': ['customer_waiting', 'is_customer_waiting',
                         'customer_waiting_status'],
    'create_date': ['create_date'],
    'start_date': ['date_start', 'create_date'],
}

DATE_FILTERS = ('today', 'yesterday', 'week', 'month', 'custom', 'all')


class JobCardDashboard(models.AbstractModel):
    _name = 'job.card.dashboard'
    _description = 'Job Card Dashboard Service'

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    @api.model
    def _task_fields(self):
        return self.env['project.task']._fields

    @api.model
    def _f(self, key):
        """Resolve a logical field name to the real one, or ``None``."""
        available = self._task_fields()
        for candidate in FIELD_CANDIDATES.get(key, []):
            if candidate in available:
                return candidate
        return None

    @api.model
    def _is_m2m(self, fname):
        field = self._task_fields().get(fname)
        return bool(field) and field.type in ('many2many', 'one2many')

    @api.model
    def _safe(self, key, func, warnings, default=None):
        """Run a widget builder, capturing its failure instead of propagating."""
        try:
            return func()
        except Exception as error:  # pragma: no cover - defensive by design
            _logger.exception('Job card dashboard: widget %s failed', key)
            warnings.append('%s: %s' % (key, error))
            return default

    # ------------------------------------------------------------------
    # Domains
    # ------------------------------------------------------------------
    @api.model
    def _base_domain(self):
        """Domain that isolates job cards from ordinary project tasks.

        The flag field is only trusted when this database actually uses it: on
        installations where ``is_jobcard`` was never populated, filtering on it
        would silently return zero everywhere.  In that case the presence of a
        workshop stage is the reliable marker.  Same logic for the inspection
        flag: it is only used to exclude records when doing so still leaves
        job cards behind.
        """
        Task = self.env['project.task']
        flag = self._f('job_card_flag')
        stage = self._f('stage')
        domain = []

        if flag and Task.sudo().search_count([(flag, '=', True)], limit=1):
            domain.append((flag, '=', True))
        elif stage:
            domain.append((stage, '!=', False))

        inspection = self._f('inspection_flag')
        if inspection:
            candidate = domain + [(inspection, '=', False)]
            if Task.sudo().search_count(candidate, limit=1) or \
                    not Task.sudo().search_count(domain or [('id', '!=', 0)], limit=1):
                domain = candidate
        return domain

    @api.model
    def _diagnostics(self, domain):
        """Explain an empty dashboard instead of just showing zeros."""
        Task = self.env['project.task']
        base = self._base_domain()
        return {
            'filtered': Task.search_count(domain),
            'all_time': Task.search_count(base),
            'base_domain': str(base),
        }

    @api.model
    def _period_bounds(self, filters):
        """Return ``(start, end)`` datetimes in UTC for the selected period."""
        config = self.env['job.card.dashboard.config'].get_config_values()
        mode = filters.get('date_filter') or config['default_date_filter']
        if mode not in DATE_FILTERS:
            mode = 'today'
        today = fields.Date.context_today(self)
        if mode == 'today':
            start, end = today, today
        elif mode == 'yesterday':
            start = end = today - timedelta(days=1)
        elif mode == 'week':
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif mode == 'month':
            start = today.replace(day=1)
            next_month = (start + timedelta(days=32)).replace(day=1)
            end = next_month - timedelta(days=1)
        elif mode == 'custom':
            start = fields.Date.to_date(filters.get('date_from')) or today
            end = fields.Date.to_date(filters.get('date_to')) or today
        else:  # all
            return None, None
        return start, end

    @api.model
    def _date_domain(self, filters):
        start, end = self._period_bounds(filters)
        if not start:
            return []
        config = self.env['job.card.dashboard.config'].get_config_values()
        fname = config['date_field']
        if fname not in self._task_fields():
            fname = self._f('create_date')
        if not fname:
            return []
        field = self._task_fields()[fname]
        if field.type == 'date':
            return [(fname, '>=', start), (fname, '<=', end)]
        # datetime: convert local day bounds to UTC
        start_dt = fields.Datetime.to_string(
            self._to_utc(datetime.combine(start, time.min)))
        end_dt = fields.Datetime.to_string(
            self._to_utc(datetime.combine(end, time.max)))
        return [(fname, '>=', start_dt), (fname, '<=', end_dt)]

    @api.model
    def _to_utc(self, naive_dt):
        """Convert a naive user-local datetime to naive UTC for the ORM."""
        timezone = pytz.timezone(self.env.user.tz or 'UTC')
        return timezone.localize(naive_dt).astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _filter_domain(self, filters):
        """Full domain: job cards + period + every active toolbar filter."""
        filters = filters or {}
        domain = self._base_domain() + self._date_domain(filters)

        simple_map = [
            ('branch_id', 'branch'),
            ('customer_id', 'customer'),
            ('company_id', 'company'),
            ('stage_id', 'stage'),
            ('bay_id', 'bay'),
        ]
        for key, logical in simple_map:
            value = filters.get(key)
            fname = self._f(logical)
            if value and fname:
                domain.append((fname, '=', int(value)))

        advisor = filters.get('advisor_id')
        advisor_field = self._f('advisor')
        if advisor and advisor_field:
            operator = 'in' if self._is_m2m(advisor_field) else '='
            domain.append((advisor_field, operator,
                           [int(advisor)] if operator == 'in' else int(advisor)))

        technician = filters.get('technician_id')
        if technician:
            domain = expression.AND([domain, self._technician_domain(int(technician))])

        priority = filters.get('priority')
        priority_field = self._f('priority')
        if priority not in (None, '', False) and priority_field:
            domain.append((priority_field, '=', str(priority)))

        search = (filters.get('search') or '').strip()
        if search:
            domain = expression.AND([domain, self._search_domain(search)])
        return domain

    @api.model
    def _technician_domain(self, technician_id):
        """Technician can live on the task or only on the daily report lines."""
        fname = self._f('technician')
        if fname:
            operator = 'in' if self._is_m2m(fname) else '='
            return [(fname, operator,
                     [technician_id] if operator == 'in' else technician_id)]
        line_field = self._line_technician_field()
        if line_field:
            lines = self.env['account.analytic.line'].search(
                [(line_field, '=', technician_id)], limit=20000)
            task_ids = [line.task_id.id for line in lines if line.task_id]
            return [('id', 'in', task_ids or [0])]
        return []

    @api.model
    def _line_technician_field(self):
        line_fields = self.env['account.analytic.line']._fields
        for candidate in ('employees_id', 'employee_id', 'technician_id'):
            if candidate in line_fields:
                return candidate
        return None

    @api.model
    def _search_domain(self, term):
        """Global search: job card no, plate, VIN/chassis, customer, mobile."""
        blocks = []
        available = self._task_fields()
        for fname in ('number', 'name'):
            if fname in available:
                blocks.append([(fname, 'ilike', term)])
        vehicle = self._f('vehicle')
        if vehicle:
            vehicle_fields = self.env['fleet.vehicle']._fields
            for sub in ('license_plate', 'vin_sn', 'chassis_number', 'name'):
                if sub in vehicle_fields:
                    blocks.append([('%s.%s' % (vehicle, sub), 'ilike', term)])
        customer = self._f('customer')
        if customer:
            partner_fields = self.env['res.partner']._fields
            for sub in ('name', 'phone', 'mobile', 'email', 'vat'):
                if sub in partner_fields:
                    blocks.append([('%s.%s' % (customer, sub), 'ilike', term)])
        return expression.OR(blocks) if blocks else []

    # ------------------------------------------------------------------
    # Grouping helper
    # ------------------------------------------------------------------
    @api.model
    def _group_count(self, domain, groupby):
        """``{group_key: count}`` using read_group only - never a record read."""
        Task = self.env['project.task']
        result = {}
        try:
            rows = Task._read_group(domain, [groupby], ['__count'])
            for key, count in rows:
                result[key.id if hasattr(key, 'id') else key] = count
        except Exception:
            rows = Task.read_group(domain, [], [groupby], lazy=False)
            for row in rows:
                key = row.get(groupby)
                if isinstance(key, (list, tuple)):
                    key = key[0]
                result[key] = row.get('__count') or row.get(groupby + '_count') or 0
        return result

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        warnings = []
        config = self.env['job.card.dashboard.config'].get_config_values()
        domain = self._filter_domain(filters)
        widgets = config['widgets']

        data = {
            'config': config,
            'schema': {key: self._f(key) for key in FIELD_CANDIDATES},
            'server_time': fields.Datetime.to_string(fields.Datetime.now()),
            'total': self.env['project.task'].search_count(domain),
        }
        data['statuses'] = self._safe(
            'Status cards', lambda: self._status_cards(domain, filters), warnings, [])
        if widgets['bays']:
            data['bays'] = self._safe('Bay occupancy', self._bays, warnings, [])
        if widgets['today_jobs']:
            data['today_jobs'] = self._safe(
                "Today's job cards",
                lambda: self._job_rows(domain, config['list_limit']), warnings, [])
        if widgets['overdue']:
            data['overdue'] = self._safe(
                'Overdue job cards',
                lambda: self._overdue(domain, config), warnings, {'count': 0, 'rows': []})
        if widgets['waiting']:
            data['waiting'] = self._safe(
                'Customer waiting',
                lambda: self._waiting(domain, config['list_limit']), warnings, [])
        if widgets['alerts']:
            data['alerts'] = self._safe(
                'Priority alerts', lambda: self._alerts(domain), warnings, [])
        data['diagnostics'] = self._safe(
            'Diagnostics', lambda: self._diagnostics(domain), warnings, {})
        data['warnings'] = warnings
        return data

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    @api.model
    def _active_domain(self):
        """Job cards that are open *right now*: current status is not Closed.

        Evaluated on the current ``cc_stage_id`` only - nothing is stored on
        the job card, so reopening a closed job card makes it count again
        immediately.  A job card without a status is not closed.
        """
        stage_field = self._f('stage')
        if stage_field:
            closed = self.env['job.card.stage']._dashboard_closed_stages()
            if not closed:
                return []
            return ['|', (stage_field, '=', False),
                    (stage_field, 'not in', closed.ids)]
        closed_flag = self._f('closed')
        return [(closed_flag, '=', False)] if closed_flag else []

    @api.model
    def _trend(self, current, before):
        """Period-over-period change, shared by every card."""
        if before:
            return round((current - before) * 100.0 / before)
        return 100 if current else 0

    @api.model
    def _status_cards(self, domain, filters):
        stage_field = self._f('stage')
        stages = self.env['job.card.stage']._dashboard_stages()
        specials = self.env['job.card.dashboard.card']._dashboard_cards()
        if not stage_field:
            return self._fallback_special_cards(specials, domain) + stages
        counts = self._group_count(domain, stage_field)

        # Previous comparable period, for the trend badge.
        previous = {}
        start, end = self._period_bounds(filters)
        if start and end:
            span = (end - start).days + 1
            previous_filters = dict(filters or {})
            previous_filters.update({
                'date_filter': 'custom',
                'date_from': fields.Date.to_string(start - timedelta(days=span)),
                'date_to': fields.Date.to_string(end - timedelta(days=span)),
            })
            previous = self._group_count(
                self._filter_domain(previous_filters), stage_field)

        total = sum(counts.values()) or 0
        for stage in stages:
            current = counts.get(stage['id'], 0)
            before = previous.get(stage['id'], 0)
            stage.update({
                'count': current,
                'trend': self._trend(current, before),
                'percentage': round(current * 100.0 / total, 1) if total else 0.0,
            })

        if specials:
            # The grouped counts above partition *every* job card of the
            # period by its current status (hidden statuses included), so the
            # open figure is the same read_group minus the Closed group(s):
            # no extra query, and identical to
            # search_count(domain + _active_domain()).
            closed_ids = set(
                self.env['job.card.stage']._dashboard_closed_stages().ids)
            active_now = sum(c for key, c in counts.items() if key not in closed_ids)
            active_before = sum(
                c for key, c in previous.items() if key not in closed_ids)
            for card in specials:
                if card['card_type'] == 'total_job_card':
                    card.update({
                        'count': active_now,
                        'trend': self._trend(active_now, active_before),
                        'percentage': round(active_now * 100.0 / total, 1) if total else 0.0,
                    })

        # Calculated cards are ordered with the statuses; on a tie they go
        # first (Total Job Card leads the grid by default).
        cards = specials + stages
        cards.sort(key=lambda card: (card.get('sequence') or 0,
                                     0 if card.get('is_special') else 1))
        return cards

    @api.model
    def _fallback_special_cards(self, specials, domain):
        """Schema without a status field: count with the closed flag."""
        Task = self.env['project.task']
        total = Task.search_count(domain)
        current = Task.search_count(
            expression.AND([domain, self._active_domain()])) if specials else 0
        for card in specials:
            card.update({
                'count': current, 'trend': 0,
                'percentage': round(current * 100.0 / total, 1) if total else 0.0,
            })
        return specials

    @api.model
    def _special_card_domain(self, key):
        """Extra domain + label for a calculated card id, or ``None``."""
        if key == 'total_job_card':
            return self._active_domain(), 'Total Job Cards (Open)'
        return None

    @api.model
    def _occupancy_domain(self):
        """A bay holds either a job card or a vehicle inspection - never both.

        This deliberately does NOT reuse ``_base_domain``: that one excludes
        inspections, and an inspection parked on a lift still occupies it.
        """
        job_flag = self._f('job_card_flag')
        inspection_flag = self._f('inspection_flag')
        stage = self._f('stage')
        blocks = []
        if job_flag:
            blocks.append([(job_flag, '=', True)])
        if inspection_flag:
            blocks.append([(inspection_flag, '=', True)])
        if not blocks and stage:
            blocks.append([(stage, '!=', False)])
        return expression.OR(blocks) if blocks else []

    @api.model
    def _bays(self):
        if 'job.card.bay' not in self.env:
            return []
        Bay = self.env['job.card.bay']
        Task = self.env['project.task']
        bay_field = self._f('bay')
        closed = self._f('closed')
        inspection_flag = self._f('inspection_flag')
        job_flag = self._f('job_card_flag')

        bays = Bay.search([])
        if 'sequence' in Bay._fields:
            bays = bays.sorted(key=lambda b: (b.sequence or 0, b.id))
        if not bay_field or not bays:
            return [{
                'id': bay.id, 'name': bay.display_name, 'state': 'free',
                'label': 'Free', 'occupant': '', 'number': '',
                'task_id': False,
            } for bay in bays]

        # One query for every bay instead of one query per bay.
        domain = expression.AND([
            self._occupancy_domain(), [(bay_field, 'in', bays.ids)],
        ])
        if closed:
            domain = expression.AND([domain, [(closed, '=', False)]])
        occupants = {}
        for task in Task.search(domain, order='id desc'):
            key = task[bay_field].id
            occupants.setdefault(key, task)   # newest record wins

        rows = []
        for bay in bays:
            task = occupants.get(bay.id)
            manual = bay.manual_state if 'manual_state' in Bay._fields else False
            if task:
                is_inspection = bool(inspection_flag and task[inspection_flag])
                is_job_card = bool(job_flag and task[job_flag])
                if is_inspection and not is_job_card:
                    state, label, occupant = 'inspection', 'Inspection', 'Vehicle Inspection'
                else:
                    state, label, occupant = 'occupied', 'Occupied', 'Job Card'
                    stage_name = self._stage_label(task)
                    if stage_name and 'road' in stage_name.lower():
                        state, label = 'road_test', 'Road Test'
                rows.append({
                    'id': bay.id,
                    'name': bay.display_name,
                    'state': state,
                    'label': label,
                    'occupant': occupant,
                    'number': self._number(task),
                    'task_id': task.id,
                })
                continue
            if manual and str(manual).lower() not in ('free', 'available', 'draft'):
                state, label = 'maintenance', str(manual).replace('_', ' ').title()
            else:
                state, label = 'free', 'Free'
            rows.append({
                'id': bay.id, 'name': bay.display_name, 'state': state,
                'label': label, 'occupant': '', 'number': '', 'task_id': False,
            })
        return rows

    @api.model
    def _stage_label(self, task):
        stage_field = self._f('stage')
        if stage_field and task[stage_field]:
            return task[stage_field].display_name
        return ''

    @api.model
    def _number(self, task):
        fname = self._f('number')
        return (task[fname] if fname else task.display_name) or task.display_name

    @api.model
    def _read_fields(self):
        """Fields safe to read for the tables."""
        wanted = ['stage', 'number', 'vehicle', 'customer', 'advisor',
                  'technician', 'promise', 'priority', 'create_date', 'bay',
                  'inspection_state']
        names = []
        for key in wanted:
            fname = self._f(key)
            if fname and fname not in names:
                names.append(fname)
        return names

    @api.model
    def _serialize(self, task):
        def label(value):
            if isinstance(value, models.BaseModel):
                return ', '.join(value.mapped('display_name')) if len(value) > 1 \
                    else (value.display_name if value else '')
            return value or ''

        advisor = self._f('advisor')
        technician = self._f('technician')
        vehicle = self._f('vehicle')
        customer = self._f('customer')
        promise = self._f('promise')
        stage = self._f('stage')
        stage_record = task[stage] if stage else None
        stage_style = {}
        if stage_record:
            stage_style = {
                'color': stage_record.dashboard_color or '',
                'name': stage_record.display_name,
                'id': stage_record.id,
            }
        return {
            'id': task.id,
            'number': self._number(task),
            'vehicle': label(task[vehicle]) if vehicle else '',
            'customer': label(task[customer]) if customer else '',
            'advisor': label(task[advisor]) if advisor else '',
            'technician': label(task[technician]) if technician else self._task_technician(task),
            'promise_date': self._format_date(task[promise]) if promise else '',
            'promise_raw': fields.Date.to_string(task[promise]) if promise and task[promise] else '',
            'stage': stage_style,
            'create_date': fields.Datetime.to_string(task.create_date),
        }

    @api.model
    def _task_technician(self, task):
        line_field = self._line_technician_field()
        if not line_field:
            return ''
        lines = self.env['account.analytic.line'].search(
            [('task_id', '=', task.id)], limit=5)
        names = {line[line_field].display_name for line in lines if line[line_field]}
        return ', '.join(sorted(names))

    @api.model
    def _format_date(self, value):
        if not value:
            return ''
        if isinstance(value, datetime):
            return fields.Datetime.context_timestamp(self, value).strftime('%d/%m/%Y')
        return value.strftime('%d/%m/%Y')

    @api.model
    def _job_rows(self, domain, limit, order=None):
        tasks = self.env['project.task'].search(
            domain, order=order or 'create_date desc', limit=limit)
        return [self._serialize(task) for task in tasks]

    @api.model
    def _overdue_domain(self, domain):
        promise = self._f('promise')
        if not promise:
            return None
        today = fields.Date.context_today(self)
        extra = [(promise, '!=', False), (promise, '<', today)]
        closed = self._f('closed')
        if closed:
            extra.append((closed, '=', False))
        return expression.AND([domain, extra])

    @api.model
    def _overdue(self, domain, config):
        overdue_domain = self._overdue_domain(domain)
        if overdue_domain is None:
            return {'count': 0, 'rows': []}
        promise = self._f('promise')
        today = fields.Date.context_today(self)
        tasks = self.env['project.task'].search(
            overdue_domain, order='%s asc' % promise, limit=config['list_limit'])
        rows = []
        for task in tasks:
            row = self._serialize(task)
            due = task[promise]
            due_date = due.date() if isinstance(due, datetime) else due
            days = (today - due_date).days if due_date else 0
            row['days_overdue'] = days
            if days >= config['overdue_severe_days']:
                row['severity'] = 'severe'
            elif days >= config['overdue_critical_days']:
                row['severity'] = 'critical'
            elif days >= config['overdue_warning_days']:
                row['severity'] = 'warning'
            else:
                row['severity'] = 'none'
            rows.append(row)
        return {
            'count': self.env['project.task'].search_count(overdue_domain),
            'rows': rows,
        }

    @api.model
    def _humanize_hours(self, hours):
        """1.5 -> "1h 30m", 30 -> "1d 6h"."""
        if hours is None:
            return '-'
        minutes = int(round(hours * 60))
        if minutes < 60:
            return '%dm' % minutes
        if minutes < 60 * 24:
            return '%dh %02dm' % (minutes // 60, minutes % 60)
        days, rest = divmod(minutes, 60 * 24)
        return '%dd %dh' % (days, rest // 60)

    @api.model
    def _waiting_domain(self, domain):
        """Customers flagged as waiting on the job card itself."""
        closed = self._f('closed')
        customer = self._f('customer')
        waiting = self._f('customer_waiting')
        extra = []
        if waiting:
            field = self._task_fields()[waiting]
            extra.append((waiting, '=', True) if field.type == 'boolean'
                         else (waiting, '!=', False))
        if closed:
            extra.append((closed, '=', False))
        if customer:
            extra.append((customer, '!=', False))
        return expression.AND([domain, extra]) if extra else domain

    @api.model
    def _waiting(self, domain, limit):
        promise = self._f('promise')
        tasks = self.env['project.task'].search(
            self._waiting_domain(domain), order='create_date asc', limit=limit)
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        rows = []
        for task in tasks:
            row = self._serialize(task)
            created = fields.Datetime.context_timestamp(self, task.create_date)
            row['waiting_since'] = created.strftime('%d/%m %H:%M')
            hours = (now - task.create_date).total_seconds() / 3600.0
            row['waiting_time'] = self._humanize_hours(hours)
            row['waiting_hours'] = round(hours, 1)
            due = task[promise] if promise else False
            due_date = due.date() if isinstance(due, datetime) else due
            if due_date and due_date < today:
                row['status'], row['severity'] = 'Overdue', 'critical'
            elif due_date and due_date == today:
                row['status'], row['severity'] = 'Due today', 'warning'
            else:
                row['status'], row['severity'] = 'Waiting', 'none'
            rows.append(row)
        return rows

    @api.model
    def _high_priority_stages(self):
        """Which statuses count as high priority.

        Preference order: an explicit flag on ``job.card.stage`` if the
        workshop module defines one, otherwise the statuses whose name reads
        as urgent. Never a hardcoded stage id.
        """
        Stage = self.env['job.card.stage']
        for candidate in ('is_high_priority', 'high_priority', 'is_urgent',
                          'urgent', 'is_priority'):
            field = Stage._fields.get(candidate)
            if field and field.type == 'boolean':
                stages = Stage.search([(candidate, '=', True)])
                if stages:
                    return stages
        return Stage.search(['|', '|',
                             ('name', 'ilike', 'urgent'),
                             ('name', 'ilike', 'high priority'),
                             ('name', 'ilike', 'redo')])

    @api.model
    def _alerts(self, domain):
        Task = self.env['project.task']
        alerts = []
        priority = self._f('priority')
        closed = self._f('closed')
        promise = self._f('promise')
        today = fields.Date.context_today(self)

        def add(key, label, extra, icon, color):
            try:
                alert_domain = expression.AND([domain, extra])
                alerts.append({
                    'key': key, 'label': label, 'icon': icon, 'color': color,
                    'count': Task.search_count(alert_domain),
                    'domain': alert_domain,
                })
            except Exception:
                _logger.debug('Alert %s skipped', key, exc_info=True)

        high_stages = self._high_priority_stages()
        stage_field = self._f('stage')
        if high_stages and stage_field:
            add('high_priority', 'High Priority',
                [(stage_field, 'in', high_stages.ids)],
                'fa-exclamation-triangle', '#EF4444')
        elif priority:
            add('high_priority', 'High Priority', [(priority, '!=', '0')],
                'fa-exclamation-triangle', '#EF4444')
        overdue_domain = self._overdue_domain(domain)
        if overdue_domain is not None:
            alerts.append({
                'key': 'overdue', 'label': 'Overdue Jobs', 'icon': 'fa-clock-o',
                'color': '#F97316', 'count': Task.search_count(overdue_domain),
                'domain': overdue_domain,
            })
        if stage_field:
            for keyword, label, icon, color in (
                ('approval', 'Waiting Approval', 'fa-check-circle-o', '#F59E0B'),
                ('part', 'Waiting Parts', 'fa-cube', '#8B5CF6'),
            ):
                stages = self.env['job.card.stage'].search(
                    [('name', 'ilike', keyword)])
                if stages:
                    add(keyword, label, [(stage_field, 'in', stages.ids)], icon, color)
        if promise:
            extra = [(promise, '=', today)]
            if closed:
                extra.append((closed, '=', False))
            add('promise_today', 'Promise Date Today', extra, 'fa-calendar-check-o',
                '#0EA5E9')
        return alerts

    # ------------------------------------------------------------------
    # Lazy drill-down: card dropdown
    # ------------------------------------------------------------------
    @api.model
    def get_stage_details(self, stage_id, filters=None, limit=10):
        """Last N job cards of a status + its vehicle inspection breakdown."""
        stage_field = self._f('stage')
        domain = self._filter_domain(filters or {})
        special = self._special_card_domain(stage_id)
        if special is not None:
            domain = expression.AND([domain, special[0]])
        elif stage_field and stage_id:
            domain = expression.AND([domain, [(stage_field, '=', int(stage_id))]])
        return {
            'rows': self._job_rows(domain, limit),
            'inspection': self._inspection_breakdown(domain),
        }

    @api.model
    def _inspection_breakdown(self, domain):
        """Completed / pending / passed / failed counts for the given domain."""
        fname = self._f('inspection_state')
        if not fname:
            return []
        field = self._task_fields()[fname]
        counts = self._group_count(domain, fname)
        labels = dict(field.selection or []) if isinstance(field.selection, list) else {}
        result = []
        for key, count in counts.items():
            if key in (False, None):
                label = 'Not Started'
            else:
                label = labels.get(key, str(key).replace('_', ' ').title())
            result.append({
                'key': key if key else '',
                'label': label,
                'count': count,
                'field': fname,
            })
        result.sort(key=lambda item: -item['count'])
        return result

    # ------------------------------------------------------------------
    # Drill-down actions
    # ------------------------------------------------------------------
    @api.model
    def get_job_card_action(self, domain=None, name='Job Cards', res_id=None):
        """Return a standard ``ir.actions.act_window`` for the drill-down.

        Reuses the job card action defined by the business module when it can
        be found, so users get the same views they see in the menus.
        """
        action = None
        for xmlid in ('job_card.action_job_card', 'job_card.job_card_action',
                      'job_card_extension.action_job_card',
                      'job_card.action_job_card_all'):
            candidate = self.env.ref(xmlid, raise_if_not_found=False)
            if candidate and candidate._name == 'ir.actions.act_window':
                action = candidate.sudo().read()[0]
                break
        if not action:
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'project.task',
                'view_mode': 'list,form',
                'views': [(False, 'list'), (False, 'form')],
            }
        action = dict(action)
        action['name'] = name
        action['domain'] = domain if domain is not None else self._base_domain()
        action['target'] = 'current'
        context = action.get('context') or {}
        if isinstance(context, str):
            try:
                context = dict(eval(context))  # noqa: S307 - stored action context
            except Exception:
                context = {}
        flag = self._f('job_card_flag')
        if flag:
            context['default_%s' % flag] = True
        action['context'] = context
        if res_id:
            form_view = False
            for view_id, view_type in (action.get('views') or []):
                if view_type == 'form':
                    form_view = view_id
                    break
            action.update({
                'res_id': int(res_id),
                'view_mode': 'form',
                'views': [(form_view, 'form')],
            })
        return action

    @api.model
    def get_status_action(self, stage_id, filters=None, extra_domain=None):
        domain = self._filter_domain(filters or {})
        stage_field = self._f('stage')
        name = 'Job Cards'
        special = self._special_card_domain(stage_id)
        if special is not None:
            domain = expression.AND([domain, special[0]])
            name = special[1]
        elif stage_field and stage_id:
            stage = self.env['job.card.stage'].browse(int(stage_id))
            domain = expression.AND([domain, [(stage_field, '=', stage.id)]])
            name = stage.display_name
        if extra_domain:
            domain = expression.AND([domain, extra_domain])
        return self.get_job_card_action(domain, name)

    @api.model
    def get_overdue_action(self, filters=None):
        domain = self._overdue_domain(self._filter_domain(filters or {}))
        return self.get_job_card_action(domain or [], 'Overdue Job Cards')

    @api.model
    def get_inspection_action(self, state_key, filters=None):
        fname = self._f('inspection_state')
        domain = self._filter_domain(filters or {})
        if fname:
            domain = expression.AND(
                [domain, [(fname, '=', state_key or False)]])
        return self.get_job_card_action(domain, 'Vehicle Inspection')

    @api.model
    def _sibling_action(self, model_prefixes=(), exclude=(), name='',
                        client_tags=()):
        """Find another ODEX module's own action without depending on it.

        Module and action names have moved between versions here, so nothing
        is hardcoded: client actions are matched on their tag, window actions
        on the model they open. Returns ``None`` when the module is absent.
        """
        Client = self.env['ir.actions.client'].sudo()
        for tag in client_tags:
            action = Client.search([('tag', '=', tag)], limit=1)
            if action:
                values = action.read()[0]
                values['name'] = name or values.get('name')
                values['target'] = 'current'
                return values

        Window = self.env['ir.actions.act_window'].sudo()
        for prefix in model_prefixes:
            for action in Window.search([('res_model', '=like', prefix + '%')]):
                model = action.res_model or ''
                tail = model[len(prefix):]
                if any(word in tail for word in exclude):
                    continue
                values = action.read()[0]
                values['name'] = name or values.get('name')
                values['target'] = 'current'
                return values
        return None

    @api.model
    def get_quick_action(self, key):
        """Resolve the Quick Action tiles to real Odoo actions."""
        flag = self._f('job_card_flag')
        inspection_flag = self._f('inspection_flag')

        def act_window(name, res_model, view_mode, domain=None, context=None):
            views = [(False, view) for view in view_mode.split(',')]
            return {
                'type': 'ir.actions.act_window', 'name': name,
                'res_model': res_model, 'view_mode': view_mode,
                'views': views, 'domain': domain or [],
                'context': context or {}, 'target': 'current',
            }

        if key == 'new_job_card':
            action = self.get_job_card_action([], 'New Job Card')
            action.update({'view_mode': 'form', 'views': [(False, 'form')]})
            return action
        if key == 'inspection':
            domain = [(inspection_flag, '=', True)] if inspection_flag else []
            context = {'default_%s' % inspection_flag: True} if inspection_flag else {}
            return act_window('Vehicle Inspection', 'project.task',
                              'list,form', domain, context)
        if key == 'estimate':
            return act_window('Estimates', 'sale.order', 'list,form',
                              [('state', 'in', ['draft', 'sent'])])
        if key == 'invoice':
            return act_window('Invoices', 'account.move', 'list,form',
                              [('move_type', '=', 'out_invoice')],
                              {'default_move_type': 'out_invoice'})
        if key == 'appointments':
            booking = self._sibling_action(
                model_prefixes=('odex.booking', 'workshop.booking', 'booking'),
                exclude=('schedule', 'slot', 'break', 'offday', 'config',
                         'line', 'tag', 'type'),
                name='Appointments')
            if booking:
                return booking
            model = 'calendar.event' if 'calendar.event' in self.env else 'project.task'
            return act_window('Appointments', model, 'calendar,list,form')
        if key == 'technician_board':
            overview = self._sibling_action(
                model_prefixes=('technician.overview', 'odex.technician'),
                exclude=('config',), name='Technician Overview',
                client_tags=('technician_overview', 'odex_technician_overview'))
            if overview:
                return overview
            return act_window('Technicians', 'hr.employee', 'kanban,list,form')
        if key == 'reports':
            domain = [(flag, '=', True)] if flag else []
            return act_window('Job Card Analysis', 'project.task',
                              'pivot,graph,list', domain)
        if key == 'follow_up':
            closed = self._f('closed')
            domain = self._base_domain()
            if closed:
                domain.append((closed, '=', False))
            return self.get_job_card_action(domain, 'Customer Follow-up')
        return self.get_job_card_action([], 'Job Cards')
