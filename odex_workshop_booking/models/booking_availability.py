# -*- coding: utf-8 -*-
"""Live availability: the working schedule IS the source of truth.

Previously the module pre-generated a physical ``odex.booking.slot`` row for
every half hour of every day — thousands of records that immediately fell out
of step whenever the schedule changed, which is why toggling a day off did
nothing until someone pressed "Apply Changes".

Here the times are derived from the schedule on demand and the bookings are
counted against them. Nothing to generate, nothing to synchronise, nothing to
go stale: change a working day and the website reflects it on the next page
load.

A real slot row is still created, but lazily — only at the moment a booking
actually takes one (see ``materialise``). Existing bookings keep working
because they keep pointing at their slot record.
"""
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


def float_to_str(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    return '%02d:%02d' % (hours, minutes)


class BookingAvailability(models.AbstractModel):
    _name = 'odex.booking.availability'
    _description = 'Booking Availability Engine'

    # ------------------------------------------------------------------
    # Schedule resolution
    # ------------------------------------------------------------------
    @api.model
    def _schedule_for(self, company):
        return self.env['odex.booking.schedule'].sudo().search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=1)

    # ------------------------------------------------------------------
    # Times implied by the schedule for one date
    # ------------------------------------------------------------------
    @api.model
    def _times_for_date(self, company, date, schedule=None):
        """[(hour_from, hour_to, capacity)] the schedule implies for a date.

        Empty when the day is closed, an off day, a holiday, or outside the
        effective range. Breaks are excluded here, so what comes back is
        exactly what a customer could book.
        """
        schedule = schedule or self._schedule_for(company)
        if not schedule:
            return []
        if schedule.date_from and date < schedule.date_from:
            return []
        if schedule.date_to and date > schedule.date_to:
            return []
        if date in set(schedule.offday_ids.mapped('date')):
            return []
        if self.env['odex.booking.holiday']._is_closed(date, company):
            return []

        day = schedule.day_ids.filtered(
            lambda d: int(d.dayofweek) == date.weekday() and d.is_working)[:1]
        if not day:
            return []

        capacity = day.capacity or schedule.default_capacity or 1
        step = int(schedule.slot_duration) / 60.0
        breaks = [(b.hour_from, b.hour_to) for b in day._breaks()]
        times = []
        current = day.hour_from
        # tolerance guards float rounding on 20/45 minute steps
        while current + step <= day.hour_to + 0.0001:
            stop = current + step
            overlaps = any(current < b_to - 0.0001 and stop > b_from + 0.0001
                           for b_from, b_to in breaks)
            if not overlaps:
                times.append((round(current, 4), round(stop, 4), capacity))
            current = stop
        return times

    # ------------------------------------------------------------------
    # Bookings already taken
    # ------------------------------------------------------------------
    @api.model
    def _booked_map(self, company, date_from, date_to):
        """{(date, hour_from): count} of bookings that consume capacity.

        One grouped query for the whole range rather than a query per day.
        """
        Booking = self.env['odex.workshop.booking'].sudo()
        # Odoo 18 requires an explicit granularity on date group-bys —
        # a bare 'booking_date' raises "Granularity not set on a date field".
        groups = Booking._read_group(
            [('company_id', '=', company.id),
             ('booking_date', '>=', date_from),
             ('booking_date', '<=', date_to),
             ('state', 'in', ('draft', 'requested', 'confirmed', 'arrived',
                              'done'))],
            ['booking_date:day', 'hour_from'], ['__count'])
        result = {}
        for booking_date, hour_from, count in groups:
            if not booking_date:
                continue
            # :day granularity yields a date (or datetime on some versions)
            day = booking_date.date() if hasattr(booking_date, 'date') \
                else booking_date
            result[(day, round(hour_from or 0.0, 4))] = count
        return result

    @api.model
    def _blocked_map(self, company, date_from, date_to):
        """{(date, hour_from)} of slot rows an administrator blocked."""
        slots = self.env['odex.booking.slot'].sudo().search([
            ('company_id', '=', company.id),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('is_blocked', '=', True),
        ])
        return {(s.date, round(s.hour_from, 4)) for s in slots}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def day_slots(self, company, date, admin=False):
        """Bookable times for a date, with their live status."""
        schedule = self._schedule_for(company)
        times = self._times_for_date(company, date, schedule)
        if not times:
            return []
        booked = self._booked_map(company, date, date)
        blocked = self._blocked_map(company, date, date)
        tz = pytz.timezone(company.booking_tz or 'UTC')
        now = fields.Datetime.now()
        notice = company.min_notice_hours or 0
        horizon = fields.Date.today() + timedelta(
            days=company.max_advance_days or 365)

        rows = []
        for hour_from, hour_to, capacity in times:
            key = (date, hour_from)
            count = booked.get(key, 0)
            remaining = max(capacity - count, 0)
            start_local = tz.localize(
                datetime.combine(date, datetime.min.time())
                + timedelta(hours=hour_from))
            start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)

            if key in blocked:
                reason = 'blocked'
            elif start_utc <= now:
                reason = 'passed'
            elif notice and start_utc <= now + timedelta(hours=notice):
                reason = 'too_soon'
            elif date > horizon:
                reason = 'beyond_horizon'
            elif remaining <= 0:
                reason = 'full'
            else:
                reason = ''

            state = ('blocked' if key in blocked
                     else 'full' if remaining <= 0
                     else 'limited' if count else 'available')
            rows.append({
                'date': fields.Date.to_string(date),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'label': float_to_str(hour_from),
                'label_to': float_to_str(hour_to),
                'period': 'morning' if hour_from < 12 else 'afternoon',
                'capacity': capacity,
                'booked': count,
                'remaining': remaining,
                'state': state,
                'bookable': admin or not reason,
                'reason': reason,
                'reason_label': {
                    'passed': _('Passed'), 'too_soon': _('Too soon'),
                    'blocked': _('Unavailable'), 'full': _('Fully Booked'),
                    'beyond_horizon': _('Not open yet'),
                }.get(reason, ''),
            })
        return rows

    @api.model
    def month_availability(self, company, year, month, admin=False):
        """{'YYYY-MM-DD': status} for a month, plus the reason per day."""
        first = fields.Date.to_date('%s-%02d-01' % (year, month))
        last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        schedule = self._schedule_for(company)
        booked = self._booked_map(company, first, last)
        blocked = self._blocked_map(company, first, last)
        today = fields.Date.today()
        horizon = today + timedelta(days=company.max_advance_days or 365)
        notice = company.min_notice_hours or 0
        tz = pytz.timezone(company.booking_tz or 'UTC')
        now = fields.Datetime.now()

        days, reasons = {}, {}
        current = first
        while current <= last:
            key = fields.Date.to_string(current)
            times = self._times_for_date(company, current, schedule)
            if not times:
                days[key] = 'closed'
                reasons[key] = 'closed'
            elif not admin and current < today:
                days[key] = 'closed'
                reasons[key] = 'past'
            elif not admin and current > horizon:
                days[key] = 'closed'
                reasons[key] = 'beyond_horizon'
            else:
                free = taken = 0
                for hour_from, _hour_to, capacity in times:
                    slot_key = (current, hour_from)
                    if slot_key in blocked:
                        continue
                    count = booked.get(slot_key, 0)
                    taken += count
                    remaining = max(capacity - count, 0)
                    if remaining <= 0:
                        continue
                    if not admin:
                        start_local = tz.localize(
                            datetime.combine(current, datetime.min.time())
                            + timedelta(hours=hour_from))
                        start_utc = start_local.astimezone(
                            pytz.utc).replace(tzinfo=None)
                        if start_utc <= now + timedelta(hours=notice):
                            continue
                    free += remaining
                if free <= 0:
                    days[key] = 'full'
                    reasons[key] = 'capacity' if taken else 'notice_window'
                elif taken:
                    days[key] = 'limited'
                else:
                    days[key] = 'available'
            current += timedelta(days=1)
        return {'days': days, 'reasons': reasons}

    # ------------------------------------------------------------------
    # Materialisation
    # ------------------------------------------------------------------
    @api.model
    def materialise(self, company, date, hour_from):
        """Return the real slot row for a time, creating it on first use.

        Bookings still point at ``odex.booking.slot``, so exactly one row per
        time that is actually used gets created — instead of thousands that
        are not.
        """
        Slot = self.env['odex.booking.slot'].sudo()
        hour_from = round(float(hour_from), 4)
        slot = Slot.search([
            ('company_id', '=', company.id),
            ('date', '=', date),
            ('hour_from', '=', hour_from),
        ], limit=1)
        if slot:
            return slot
        match = [t for t in self._times_for_date(company, date)
                 if t[0] == hour_from]
        if not match:
            raise UserError(_(
                'That time is not part of the working schedule for %s.')
                % date)
        _hf, hour_to, capacity = match[0]
        schedule = self._schedule_for(company)
        return Slot.create({
            'company_id': company.id,
            'schedule_id': schedule.id if schedule else False,
            'date': date,
            'hour_from': hour_from,
            'hour_to': hour_to,
            'capacity': capacity,
        })
