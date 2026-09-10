# -*- coding: utf-8 -*-
import base64
import csv
import io
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def float_to_str(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    return '%02d:%02d' % (hours, minutes)


class BookingSchedule(models.Model):
    _name = 'odex.booking.schedule'
    _description = 'Booking Working Schedule'
    _inherit = ['mail.thread']
    _order = 'company_id, date_from desc'

    _sql_constraints = [
        ('schedule_company_unique', 'unique(company_id)',
         'A working schedule already exists for this company.'),
    ]

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, tracking=True,
        default=lambda s: s._default_company(), ondelete='cascade')
    active = fields.Boolean(default=True)


    # Hours -------------------------------------------------------------

    slot_duration = fields.Selection([
        ('15', '15 Minutes'),
        ('20', '20 Minutes'),
        ('30', '30 Minutes'),
        ('45', '45 Minutes'),
        ('60', '60 Minutes'),
    ], string='Slot Duration', default='30', required=True)
    default_capacity = fields.Integer(
        string='Default Capacity per Slot', default=3, required=True)

    date_from = fields.Date(
        string='Effective From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Effective To')
    allow_overbooking = fields.Boolean(
        string='Allow Overbooking',
        help='Accept bookings beyond a slot capacity. The slot still shows as '
             'fully booked on the website but staff can force extra bookings.')

    day_ids = fields.One2many(
        'odex.booking.schedule.day', 'schedule_id', string='Working Days',
        default=lambda self: self._default_days())
    break_ids = fields.One2many(
        'odex.booking.break', 'schedule_id', string='Breaks',
        default=lambda self: self._default_breaks())
    offday_ids = fields.One2many(
        'odex.booking.offday', 'schedule_id', string='Off Days')
    offday_count = fields.Integer(compute='_compute_kpis')

    limited_threshold = fields.Integer(
        string='Limited Below', default=0,
        help='Mark a slot "Limited" once free places drop to this number or '
             'below. 0 means limited as soon as one booking exists.')



    # KPIs --------------------------------------------------------------
    working_days_label = fields.Char(compute='_compute_name')
    lunch_label = fields.Char(compute='_compute_name')

    # ------------------------------------------------------------------
    # Defaults / computes
    # ------------------------------------------------------------------
    @api.model
    def action_open_default(self):
        """Slot Management entry point.

        With a single company there is exactly one schedule, so a one-row
        list is pure friction — open the form. Multi-company databases still
        get the list.
        """
        schedules = self.search(
            [('company_id', 'in', self.env.companies.ids)])
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_workshop_booking.action_booking_schedule')
        if len(schedules) == 1:
            action.update({
                'res_id': schedules.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
            })
        elif not schedules:
            # No schedule yet: open a prefilled new one.
            action.update({
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
            })
        return action

    @api.model
    def _default_days(self):
        """Mon-Fri open 09:00-18:00, weekend closed — all editable."""
        return [(0, 0, {
            'dayofweek': str(i),
            'is_working': i < 5,
            'hour_from': 9.0,
            'hour_to': 18.0,
        }) for i in range(7)]

    @api.model
    def _default_breaks(self):
        return [(0, 0, {'name': _('Lunch'), 'hour_from': 13.0,
                        'hour_to': 14.0})]

    @api.model
    def _default_company(self):
        return self.env.user.booking_company_id or self.env.company

    @api.depends('company_id', 'day_ids.is_working', 'day_ids.dayofweek',
                 'break_ids.hour_from', 'break_ids.hour_to', 'date_from')
    def _compute_name(self):
        for rec in self:
            period = rec.date_from.strftime(' (%b %Y)') if rec.date_from else ''
            rec.name = _('Working Schedule - %s') % (
                rec.company_id.name or _('New')) + period
            open_days = rec.day_ids.filtered('is_working').sorted('dayofweek')
            rec.working_days_label = ', '.join(
                d.day_label[:3] for d in open_days) or _('None')
            breaks = rec.break_ids.filtered(lambda b: not b.day_id)
            rec.lunch_label = ', '.join(
                '%s %s-%s' % (b.name, float_to_str(b.hour_from),
                              float_to_str(b.hour_to)) for b in breaks) \
                or _('no breaks')

    @api.depends('offday_ids')
    def _compute_kpis(self):
        for rec in self:
            rec.offday_count = len(rec.offday_ids)

    def _check_config(self):
        for rec in self:
            if rec.default_capacity < 1:
                raise ValidationError(_('Default capacity must be at least 1.'))
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    _('"Effective To" cannot be earlier than "Effective From".'))

    @api.constrains('company_id')
    def _check_unique_schedule(self):
        for rec in self:
            if self.search_count([('id', '!=', rec.id),
                                  ('company_id', '=', rec.company_id.id)]):
                raise ValidationError(_(
                    'A working schedule already exists for %s.')
                    % rec.company_id.name)

    @api.onchange('company_id')
    def _onchange_company(self):
        if self.company_id and self.company_id.slot_capacity:
            self.default_capacity = self.company_id.slot_capacity

    @api.model
    def _resolve(self, company, branch=None):
        """Schedule governing a company. ``branch`` is accepted and ignored
        for backward compatibility with older callers."""
        if not company:
            return self.browse()
        return self.search([('company_id', '=', company.id),
                            ('active', '=', True)], limit=1)

    # ------------------------------------------------------------------
    # Slot generation
    # ------------------------------------------------------------------
    def _working_weekdays(self):
        """Python weekday indexes (Mon=0) that are open on this schedule."""
        self.ensure_one()
        return {int(d.dayofweek) for d in self.day_ids if d.is_working}

    def _day_config(self, weekday):
        """The configuration row for a python weekday index, or empty."""
        self.ensure_one()
        return self.day_ids.filtered(
            lambda d: int(d.dayofweek) == weekday and d.is_working)[:1]

    def _slot_ranges(self, day):
        """Yield (from, to) for one weekday, skipping every break it has.

        Breaks are applied per day, so a Tuesday tea break does not punch a
        hole in Monday. A slot is emitted only when it overlaps no break at
        all — partial overlaps are dropped rather than truncated, so every
        generated slot is exactly one slot_duration long.
        """
        self.ensure_one()
        if not day:
            return
        step = int(self.slot_duration) / 60.0
        breaks = [(b.hour_from, b.hour_to) for b in day._breaks()]
        current = day.hour_from
        # tolerance guards float rounding on 20/45 minute steps
        while current + step <= day.hour_to + 0.0001:
            stop = current + step
            overlaps = any(
                current < b_to - 0.0001 and stop > b_from + 0.0001
                for b_from, b_to in breaks)
            if not overlaps:
                yield round(current, 4), round(stop, 4)
            current = stop

    def _offday_dates(self):
        self.ensure_one()
        return set(self.offday_ids.mapped('date'))

    def _generation_dates(self):
        """Dates to generate: open weekday, not an off day, not a holiday."""
        self.ensure_one()
        date_to = self.date_to or (self.date_from + timedelta(days=30))
        weekdays = self._working_weekdays()
        offdays = self._offday_dates()
        Holiday = self.env['odex.booking.holiday']
        current = self.date_from
        while current <= date_to:
            if (current.weekday() in weekdays
                    and current not in offdays
                    and not Holiday._is_closed(current, self.company_id)):
                yield current
            current += timedelta(days=1)

    def action_add_offday(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Off Days'),
            'res_model': 'odex.booking.offday.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_schedule_id': self.id},
        }

    def action_copy_schedule(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Copy Schedule'),
            'res_model': 'odex.booking.schedule.copy',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_schedule_id': self.id},
        }

    def action_block_day(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Block Days'),
            'res_model': 'odex.booking.block.day',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_schedule_id': self.id,
                        'default_company_id': self.company_id.id,
},
        }

    def write(self, vals):
        """Mark the schedule dirty when the configuration changes.

        Slots are not regenerated implicitly: a schedule change can delete
        slots, so it must stay an explicit, reviewable action. The banner in
        the form tells the user to press Apply.
        """
        return super().write(vals)

    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'message': message,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
