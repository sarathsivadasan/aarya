# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import logging

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def float_to_str(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    return '%02d:%02d' % (hours, minutes)


class BookingSlot(models.Model):
    _name = 'odex.booking.slot'
    _description = 'Booking Time Slot'
    _order = 'date, hour_from'
    _rec_name = 'display_name'

    schedule_id = fields.Many2one(
        'odex.booking.schedule', string='Working Schedule', ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade')
    date = fields.Date(required=True, index=True)
    hour_from = fields.Float(string='Start', required=True)
    hour_to = fields.Float(string='End', required=True)
    capacity = fields.Integer(required=True, default=3)
    is_blocked = fields.Boolean(string='Block', default=False, tracking=True)
    is_break = fields.Boolean(
        string='Lunch Break', default=False,
        help='Marks the lunch window inside the day. Break rows are shown in '
             'the schedule for context and are never bookable.')
    allow_overbooking = fields.Boolean(
        related='schedule_id.allow_overbooking', store=True, readonly=True)
    line_number = fields.Integer(compute='_compute_line_number', string='#')
    is_expired = fields.Boolean(
        compute='_compute_is_expired', string='Expired',
        help='The slot start time has passed. Computed live, never stored, '
             'because it changes with the clock rather than with the data.')
    active = fields.Boolean(default=True)

    booking_ids = fields.One2many(
        'odex.workshop.booking', 'slot_id', string='Bookings',
        domain=[('state', 'not in', ('cancelled', 'no_show'))])
    booked_count = fields.Integer(
        compute='_compute_booked', store=True, string='Booked')
    remaining = fields.Integer(compute='_compute_booked', store=True)
    state = fields.Selection([
        ('available', 'Available'),
        ('limited', 'Limited'),
        ('full', 'Fully Booked'),
        ('blocked', 'Blocked'),
    ], compute='_compute_booked', store=True, string='Status')

    start_datetime = fields.Datetime(compute='_compute_datetimes', store=True)
    stop_datetime = fields.Datetime(compute='_compute_datetimes', store=True)

    _sql_constraints = [
        ('slot_unique', 'unique(company_id, date, hour_from)',
         'A slot already exists for this company/branch, date and time.'),
        ('capacity_positive', 'CHECK(capacity > 0)',
         'Slot capacity must be positive.'),
    ]

    def _compute_start_fallback(self):
        """Recompute start_datetime in memory when the stored value is unset."""
        self.ensure_one()
        if not (self.date and self.company_id):
            return False
        tz = pytz.timezone(self.company_id.booking_tz or 'UTC')
        start = tz.localize(datetime.combine(
            self.date, datetime.min.time()) + timedelta(hours=self.hour_from))
        return start.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def repair_missing_datetimes(self):
        """Rebuild stored datetimes left empty by the branch->company change.

        Runs on every upgrade (see data/cron_data.xml). Safe to re-run: it
        only touches rows that are actually missing a value.
        """
        broken = self.with_context(active_test=False).search(
            ['|', ('start_datetime', '=', False), ('stop_datetime', '=', False)])
        if not broken:
            return 0
        broken.invalidate_recordset(['start_datetime', 'stop_datetime'])
        broken.modified(['date', 'hour_from', 'hour_to', 'company_id'])
        broken._compute_datetimes()
        broken.flush_recordset()
        _logger.info('Repaired %s booking slots with missing datetimes',
                     len(broken))
        return len(broken)

    @api.depends('date', 'hour_from', 'hour_to', 'company_id.booking_tz')
    def _compute_datetimes(self):
        for rec in self:
            if not (rec.date and rec.company_id):
                rec.start_datetime = rec.stop_datetime = False
                continue
            tz = pytz.timezone(rec.company_id.booking_tz or 'UTC')
            start = tz.localize(datetime.combine(
                rec.date, datetime.min.time()) + timedelta(hours=rec.hour_from))
            stop = tz.localize(datetime.combine(
                rec.date, datetime.min.time()) + timedelta(hours=rec.hour_to))
            rec.start_datetime = start.astimezone(pytz.utc).replace(tzinfo=None)
            rec.stop_datetime = stop.astimezone(pytz.utc).replace(tzinfo=None)

    # The single definition of "this booking occupies a slot". Everything
    # (slot status, calendar dots, dashboard, website) reads this.
    CAPACITY_STATES = ('draft', 'requested', 'confirmed', 'arrived', 'done')

    @api.depends('booking_ids', 'booking_ids.state', 'capacity', 'is_blocked',
                 'schedule_id.limited_threshold')
    def _compute_booked(self):
        for rec in self:
            count = len(rec.booking_ids.filtered(
                lambda b: b.state in self.CAPACITY_STATES))
            rec.booked_count = count
            if rec.is_break:
                rec.remaining = 0
                rec.state = 'blocked'
                continue
            rec.remaining = max(rec.capacity - count, 0)
            if rec.is_blocked:
                rec.state = 'blocked'
            elif count >= rec.capacity:
                rec.state = 'full'
            elif rec.remaining <= (rec.schedule_id.limited_threshold or 0) \
                    or count > 0:
                rec.state = 'limited'
            else:
                rec.state = 'available'

    @api.depends('date', 'hour_from', 'company_id')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            start = rec.start_datetime or rec._compute_start_fallback()
            rec.is_expired = bool(start and start < now)

    def _compute_line_number(self):
        by_day = {}
        for rec in self.sorted(lambda s: (s.date or fields.Date.today(),
                                          s.hour_from)):
            key = (rec.company_id.id, rec.date)
            by_day[key] = by_day.get(key, 0) + 1
            rec.line_number = by_day[key]

    @api.depends('date', 'hour_from', 'hour_to', 'company_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s - %s (%s)' % (
                rec.date or '', float_to_str(rec.hour_from),
                float_to_str(rec.hour_to),
                rec.company_id.name or '')

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for rec in self:
            if rec.hour_from >= rec.hour_to:
                raise ValidationError('Slot start must be before slot end.')

    # ------------------------------------------------------------------
    # Availability helpers (shared by website / portal / backend)
    # ------------------------------------------------------------------
    def _is_bookable(self):
        """Slot can accept one more booking right now (notice rules applied)."""
        self.ensure_one()
        return not self._unbookable_reason()

    @api.model
    def _scope_domain(self, company, branch=None, date=None, dates=None):
        """Domain for the slots serving a company. ``branch`` is accepted and
        ignored — kept so older callers keep working."""
        domain = [('company_id', '=', company.id), ('active', '=', True)]
        if date:
            domain.append(('date', '=', date))
        if dates:
            domain += [('date', '>=', dates[0]), ('date', '<=', dates[1])]
        return domain

    @api.model
    def _unbookable_reason(self):
        """Why this slot cannot be booked, or '' when it can.

        The website used to show every unbookable slot as "Fully Booked",
        which is wrong and confusing for a slot whose time has simply passed
        or that is inside the minimum-notice window. Each case gets its own
        reason so the wizard can label it truthfully.
        """
        self.ensure_one()
        if self.is_break:
            return 'break'
        if not self.active:
            return 'inactive'
        if self.is_blocked:
            return 'blocked'
        company = self.company_id
        now = fields.Datetime.now()
        start = self.start_datetime or self._compute_start_fallback()
        if start and start <= now:
            return 'passed'
        if start and start <= now + timedelta(
                hours=company.min_notice_hours or 0):
            return 'too_soon'
        today = fields.Date.today()
        if self.date > today + timedelta(
                days=company.max_advance_days or 365):
            return 'beyond_horizon'
        if self.env['odex.booking.holiday']._is_closed(self.date, company):
            return 'holiday'
        if self.remaining <= 0:
            return 'full'
        if company.max_bookings_per_day:
            day_count = self.env['odex.workshop.booking'].search_count([
                ('company_id', '=', company.id),
                ('booking_date', '=', self.date),
                ('state', 'not in', ('cancelled', 'no_show')),
            ])
            if day_count >= company.max_bookings_per_day:
                return 'day_limit'
        return ''

    @api.model
    def get_day_slots(self, company, date, branch=None):
        """Return slot dicts for a date, grouped for the website wizard."""
        slots = self.search(
            self._scope_domain(company, branch, date=date)
            + [('is_break', '=', False)])
        labels = {
            'passed': _('Passed'),
            'too_soon': _('Too soon'),
            'blocked': _('Unavailable'),
            'holiday': _('Closed'),
            'full': _('Fully Booked'),
            'day_limit': _('Day full'),
            'beyond_horizon': _('Not open yet'),
            'inactive': _('Unavailable'),
        }
        result = []
        for slot in slots:
            reason = slot._unbookable_reason()
            result.append({
                'id': slot.id,
                'label': float_to_str(slot.hour_from),
                'label_to': float_to_str(slot.hour_to),
                'period': 'morning' if slot.hour_from < 12 else 'afternoon',
                'state': slot.state,
                'remaining': slot.remaining,
                'bookable': not reason,
                'reason': reason,
                'reason_label': labels.get(reason, ''),
            })
        return result

    @api.model
    def _day_availability(self, day_slots, company, date, branch=None,
                          admin=False):
        """Single source of truth for a day's status.

        Returns ``{'status', 'capacity', 'booked', 'free', 'bookable',
        'reason', 'slots'}``.

        For the customer view (``admin=False``) a slot only counts as free
        when ``_is_bookable()`` says so, i.e. the minimum-notice window and
        the booking horizon are applied here exactly as they are in the slot
        list. That is what keeps the calendar dot and the slots the customer
        actually sees in agreement — previously the dot was computed from
        raw capacity and could show green for a day whose slots had all
        passed the notice cut-off.
        """
        real = [s for s in day_slots if not s.is_break]
        open_slots = [s for s in real if not s.is_blocked]
        capacity = sum(s.capacity for s in open_slots)
        booked = sum(s.booked_count for s in real)
        free = sum(s.remaining for s in open_slots)
        bookable = [s for s in open_slots if s._is_bookable()] \
            if not admin else open_slots
        result = {'capacity': capacity, 'booked': booked, 'free': free,
                  'bookable': len(bookable), 'slots': real, 'reason': ''}

        today = fields.Date.today()
        max_date = today + timedelta(days=company.max_advance_days or 365)
        if not real:
            # Nothing generated for this day at all — the usual cause is a
            # schedule whose "Effective To" stopped before this date.
            result['status'] = 'closed'
            result['reason'] = 'no_slots'
        elif self.env['odex.booking.holiday']._is_closed(date, company):
            result['status'] = 'holiday'
            result['reason'] = 'holiday'
        elif not open_slots:
            result['status'] = 'closed'
            result['reason'] = 'blocked'
        elif not admin and date < today:
            result['status'] = 'closed'
            result['reason'] = 'past'
        elif not admin and date > max_date:
            result['status'] = 'closed'
            result['reason'] = 'beyond_horizon'
        elif free <= 0:
            result['status'] = 'full'
            result['reason'] = 'capacity'
        elif not admin and not bookable:
            # Capacity is free but nothing can still be booked today —
            # everything left is inside the minimum-notice window.
            result['status'] = 'full'
            result['reason'] = 'notice_window'
        elif booked > 0:
            result['status'] = 'limited'
        else:
            result['status'] = 'available'
        return result

    @api.model
    def get_month_availability(self, company, year, month, admin=False,
                               branch=None):
        """Day -> status map for the calendar (available/limited/full/closed)."""
        first = fields.Date.to_date('%04d-%02d-01' % (year, month))
        if month == 12:
            last = fields.Date.to_date('%04d-01-01' % (year + 1)) - timedelta(days=1)
        else:
            last = fields.Date.to_date('%04d-%02d-01' % (year, month + 1)) - timedelta(days=1)
        slots = self.search(
            self._scope_domain(company, branch, dates=(first, last))
            + [('is_break', '=', False)])
        Holiday = self.env['odex.booking.holiday']
        days = {}
        reasons = {}
        by_date = {}
        for slot in slots:
            by_date.setdefault(slot.date, []).append(slot)
        today = fields.Date.today()
        max_date = today + timedelta(days=company.max_advance_days or 365)
        current = first
        while current <= last:
            key = current.isoformat()
            stats = self._day_availability(
                by_date.get(current, []), company, current, branch,
                admin=admin)
            days[key] = stats['status']
            if stats['reason']:
                reasons[key] = stats['reason']
            current += timedelta(days=1)
        return days if not self.env.context.get('with_reasons') else \
            {'days': days, 'reasons': reasons}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_block(self):
        self.write({'is_blocked': True})

    def action_unblock(self):
        self.write({'is_blocked': False})

    def action_view_bookings(self):
        """Popup listing the bookings that consume this slot."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': '%s - %s' % (self.date, float_to_str(self.hour_from)),
            'res_model': 'odex.workshop.booking',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref(
                    'odex_workshop_booking.view_booking_slot_booking_list').id,
                 'list'),
                (False, 'form'),
            ],
            'domain': [('slot_id', '=', self.id)],
            'target': 'new',
            'context': {'create': False},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Keep manually added lines attached to their company schedule."""
        Schedule = self.env['odex.booking.schedule']
        for vals in vals_list:
            if vals.get('schedule_id') or not vals.get('company_id'):
                continue
            schedule = Schedule._resolve(
                self.env['res.company'].browse(vals['company_id']))
            if schedule:
                vals['schedule_id'] = schedule.id
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Dashboard helpers
    # ------------------------------------------------------------------
    @api.model
    def get_admin_day_slots(self, company_id, date, branch_id=None):
        """Slot rows for the dashboard Slot Management panel."""
        if not company_id or not date:
            return {'slots': [], 'booked': 0, 'capacity': 0}
        company = self.env['res.company'].browse(int(company_id))
        slots = self.search(self._scope_domain(company, date=date))
        labels = dict(self._fields['state'].selection)
        rows = []
        for slot in slots:
            rows.append({
                'id': slot.id,
                'label': '%s - %s' % (float_to_str(slot.hour_from),
                                      float_to_str(slot.hour_to)),
                'capacity': 0 if slot.is_break else slot.capacity,
                'booked': slot.booked_count,
                'state': 'break' if slot.is_break else slot.state,
                'state_label': _('Lunch Break') if slot.is_break
                else labels.get(slot.state, ''),
                'is_blocked': slot.is_blocked,
                'is_break': slot.is_break,
            })
        stats = self._day_availability(slots, company,
                                       fields.Date.to_date(date),
                                       admin=True)
        return {
            'slots': rows,
            'booked': stats['booked'],
            'capacity': stats['capacity'],
            'status': stats['status'],
        }

    @api.model
    def dashboard_slot_action(self, company_id, date, hour_from, action,
                              value=None):
        """Block / unblock / set capacity for a time on the dashboard.

        Times are virtual until used, so the row is materialised first — that
        is what makes "block this time" persistable without pre-generating
        every slot in the calendar.
        """
        company = self.env['res.company'].browse(int(company_id))
        slot = self.env['odex.booking.availability'].materialise(
            company, fields.Date.to_date(date), float(hour_from))
        if action == 'block':
            slot.action_block()
        elif action in ('unblock', 'open'):
            slot.action_unblock()
        elif action == 'closed':
            slot.action_block()
        elif action == 'capacity':
            capacity = int(value or 0)
            if capacity < 1:
                raise ValidationError(_('Capacity must be at least 1.'))
            if capacity < slot.booked_count:
                raise ValidationError(_(
                    'This time already has %s bookings.') % slot.booked_count)
            slot.capacity = capacity
        elif action == 'delete':
            if slot.booked_count:
                raise ValidationError(_(
                    'This time has bookings and cannot be removed. Block it '
                    'instead.'))
            # Removing the row just returns the time to the schedule default;
            # to stop offering it, close the day or add a break.
            slot.unlink()
        return True

    @api.model
    def dashboard_add_slot(self, company_id, date, hour_from, hour_to,
                           capacity, branch_id=None):
        self.create({
            'company_id': int(company_id),
            'date': date,
            'hour_from': float(hour_from),
            'hour_to': float(hour_to),
            'capacity': int(capacity or 1),
        })
        return True

    def action_open_slot(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
