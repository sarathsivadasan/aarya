# -*- coding: utf-8 -*-
"""Scheduling building blocks: per-day hours, breaks, manual off days.

The previous engine hardcoded one working window plus one lunch break for the
whole schedule. These three models replace that with configuration the
administrator can actually manage:

* ``odex.booking.schedule.day``  — one row per weekday, its own hours, can be
  marked closed independently.
* ``odex.booking.break``         — any number of breaks, either for the whole
  schedule or for one weekday.
* ``odex.booking.offday``        — specific calendar dates that are skipped,
  with no relation to which weekday they fall on.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
    ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


def float_to_str(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    return '%02d:%02d' % (hours, minutes)


class ScheduleDay(models.Model):
    _name = 'odex.booking.schedule.day'
    _description = 'Schedule Working Day'
    _order = 'dayofweek'

    schedule_id = fields.Many2one(
        'odex.booking.schedule', required=True, ondelete='cascade', index=True)
    dayofweek = fields.Selection(WEEKDAYS, required=True, string='Day')
    day_label = fields.Char(compute='_compute_day_label')
    is_working = fields.Boolean(string='Open', default=True)
    hour_from = fields.Float(string='From', default=9.0)
    hour_to = fields.Float(string='To', default=18.0)
    capacity = fields.Integer(
        string='Capacity', help='Leave 0 to use the schedule default.')
    break_ids = fields.One2many(
        'odex.booking.break', 'day_id', string='Breaks')
    hours_label = fields.Char(compute='_compute_day_label')

    _sql_constraints = [
        ('day_unique', 'unique(schedule_id, dayofweek)',
         'Each weekday can only be configured once per schedule.'),
    ]

    @api.depends('dayofweek', 'is_working', 'hour_from', 'hour_to')
    def _compute_day_label(self):
        labels = dict(WEEKDAYS)
        for rec in self:
            rec.day_label = labels.get(rec.dayofweek, '')
            rec.hours_label = '%s - %s' % (
                float_to_str(rec.hour_from), float_to_str(rec.hour_to)) \
                if rec.is_working else _('Closed')

    @api.constrains('hour_from', 'hour_to', 'is_working')
    def _check_hours(self):
        for rec in self:
            if rec.is_working and rec.hour_from >= rec.hour_to:
                raise ValidationError(_(
                    '%s: the opening time must be before the closing time.')
                    % rec.day_label)

    def _breaks(self):
        """Breaks that apply to this day: its own plus schedule-wide ones."""
        self.ensure_one()
        return self.break_ids | self.schedule_id.break_ids.filtered(
            lambda b: not b.day_id)


class ScheduleBreak(models.Model):
    _name = 'odex.booking.break'
    _description = 'Schedule Break'
    _order = 'hour_from'

    name = fields.Char(required=True, default='Break')
    schedule_id = fields.Many2one(
        'odex.booking.schedule', ondelete='cascade', index=True)
    day_id = fields.Many2one(
        'odex.booking.schedule.day', ondelete='cascade', index=True,
        help='Leave empty to apply this break to every working day.')
    hour_from = fields.Float(string='From', required=True, default=13.0)
    hour_to = fields.Float(string='To', required=True, default=14.0)
    show_in_grid = fields.Boolean(
        string='Show in Slot List', default=True,
        help='Display a divider row for this break in the time-slot table.')

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for rec in self:
            if rec.hour_from >= rec.hour_to:
                raise ValidationError(_(
                    'Break "%s": the start must be before the end.') % rec.name)

    @api.model_create_multi
    def create(self, vals_list):
        # A break created on a day line belongs to that day's schedule.
        for vals in vals_list:
            if vals.get('day_id') and not vals.get('schedule_id'):
                day = self.env['odex.booking.schedule.day'].browse(
                    vals['day_id'])
                vals['schedule_id'] = day.schedule_id.id
        return super().create(vals_list)


class ScheduleOffDay(models.Model):
    """A specific date the workshop does not operate.

    Distinct from ``odex.booking.holiday``: a holiday is a named, dated
    closure that may span a range and is shared across schedules, while an
    off day is a single date the administrator ticks off on this schedule's
    calendar. Both block slot generation.
    """
    _name = 'odex.booking.offday'
    _description = 'Schedule Off Day'
    _order = 'date'

    schedule_id = fields.Many2one(
        'odex.booking.schedule', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='schedule_id.company_id', store=True, index=True)
    date = fields.Date(required=True, index=True)
    reason = fields.Char()
    block_existing = fields.Boolean(
        string='Block Existing Slots', default=True,
        help='Immediately block any slots already generated for this date.')

    _sql_constraints = [
        ('offday_unique', 'unique(schedule_id, date)',
         'This date is already marked as an off day.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('block_existing')._apply_to_slots(True)
        return records

    def unlink(self):
        self._apply_to_slots(False)
        return super().unlink()

    def _apply_to_slots(self, block):
        """Block or release the slots already generated for these dates."""
        for rec in self:
            slots = self.env['odex.booking.slot'].search([
                ('company_id', '=', rec.company_id.id),
                ('date', '=', rec.date),
            ])
            if not slots:
                continue
            if block:
                slots.action_block()
            else:
                # Only release slots that no other off day or holiday covers.
                if not self.env['odex.booking.holiday']._is_closed(
                        rec.date, rec.company_id):
                    slots.action_unblock()
