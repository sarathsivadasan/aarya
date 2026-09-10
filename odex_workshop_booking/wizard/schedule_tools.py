# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

CONFIG_FIELDS = [
    'slot_duration', 'default_capacity', 'allow_overbooking',
    'limited_threshold',
]


class ScheduleCopy(models.TransientModel):
    _name = 'odex.booking.schedule.copy'
    _description = 'Copy Working Schedule'

    schedule_id = fields.Many2one(
        'odex.booking.schedule', required=True, readonly=True)
    mode = fields.Selection([
        ('company', 'Copy to another company'),
        ('dates', 'Copy to another date range'),
    ], default='company', required=True, string='Copy')
    target_company_id = fields.Many2one(
        'res.company', string='Target Company')
    date_from = fields.Date(string='New Effective From',
                            default=fields.Date.context_today)
    date_to = fields.Date(string='New Effective To')
    generate = fields.Boolean(string='Generate Slots Immediately', default=True)

    @api.onchange('mode')
    def _onchange_mode(self):
        self.target_company_id = False

    def _config_vals(self):
        """Scalar config plus a deep copy of the day/break configuration."""
        source = self.schedule_id
        vals = {f: source[f] for f in CONFIG_FIELDS}
        vals['day_ids'] = [(0, 0, {
            'dayofweek': day.dayofweek,
            'is_working': day.is_working,
            'hour_from': day.hour_from,
            'hour_to': day.hour_to,
            'capacity': day.capacity,
            'break_ids': [(0, 0, {
                'name': brk.name, 'hour_from': brk.hour_from,
                'hour_to': brk.hour_to, 'show_in_grid': brk.show_in_grid,
            }) for brk in day.break_ids],
        }) for day in source.day_ids]
        vals['break_ids'] = [(0, 0, {
            'name': brk.name, 'hour_from': brk.hour_from,
            'hour_to': brk.hour_to, 'show_in_grid': brk.show_in_grid,
        }) for brk in source.break_ids.filtered(lambda b: not b.day_id)]
        return vals

    def action_apply(self):
        self.ensure_one()
        source = self.schedule_id
        vals = self._config_vals()
        if self.mode == 'company':
            if not self.target_company_id:
                raise UserError(_('Select the company to copy the schedule to.'))
            company = self.target_company_id
        else:
            company = source.company_id

        vals.update({
            'company_id': company.id,
            'date_from': self.date_from or source.date_from,
            'date_to': self.date_to or source.date_to,
        })
        new_schedule = source.create(vals)
        if self.generate:
            new_schedule.action_generate_slots()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'odex.booking.schedule',
            'res_id': new_schedule.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }


class BlockDay(models.TransientModel):
    _name = 'odex.booking.block.day'
    _description = 'Block Booking Days'

    schedule_id = fields.Many2one('odex.booking.schedule', readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, string='Company',
        default=lambda self: self.env.company)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(
        required=True, default=fields.Date.context_today)
    reason = fields.Char(string='Reason')
    action = fields.Selection([
        ('block', 'Block these days'),
        ('unblock', 'Unblock these days'),
    ], default='block', required=True)
    create_closure = fields.Boolean(
        string='Also Record as Closure', default=True,
        help='Creates an emergency closure record so the days stay blocked for '
             'slots generated later.')

    def action_apply(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('"To" date cannot be earlier than "From" date.'))
        slots = self.env['odex.booking.slot'].search([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])
        if self.action == 'block':
            slots.action_block()
            if self.create_closure:
                self.env['odex.booking.holiday'].create({
                    'name': self.reason or _('Closure'),
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'company_id': self.company_id.id,
                    'closure_type': 'emergency',
                })
            message = _('%s slots blocked.') % len(slots)
        else:
            slots.action_unblock()
            message = _('%s slots unblocked.') % len(slots)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'message': message,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }


class OffDayWizard(models.TransientModel):
    """Add off days by picking a date, a range, or a repeating weekday."""
    _name = 'odex.booking.offday.wizard'
    _description = 'Add Off Days'

    schedule_id = fields.Many2one(
        'odex.booking.schedule', required=True, readonly=True)
    mode = fields.Selection([
        ('single', 'Single date'),
        ('range', 'Date range'),
        ('weekday', 'Every occurrence of a weekday'),
    ], default='single', required=True)
    date = fields.Date(default=fields.Date.context_today)
    date_from = fields.Date(default=fields.Date.context_today)
    date_to = fields.Date()
    dayofweek = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Weekday')
    reason = fields.Char()
    block_existing = fields.Boolean(
        string='Block Times Already Booked', default=True)

    def _dates(self):
        self.ensure_one()
        if self.mode == 'single':
            if not self.date:
                raise UserError(_('Pick a date.'))
            return [self.date]
        start = self.date_from or self.schedule_id.date_from
        end = self.date_to or self.schedule_id.date_to or start
        if not start or end < start:
            raise UserError(_('Give a valid date range.'))
        dates = []
        current = start
        while current <= end:
            if self.mode == 'range' or (
                    self.dayofweek and current.weekday() == int(self.dayofweek)):
                dates.append(current)
            current += timedelta(days=1)
        return dates

    def action_apply(self):
        self.ensure_one()
        if self.mode == 'weekday' and not self.dayofweek:
            raise UserError(_('Choose the weekday to close.'))
        OffDay = self.env['odex.booking.offday']
        existing = set(self.schedule_id.offday_ids.mapped('date'))
        created = 0
        for date in self._dates():
            if date in existing:
                continue
            OffDay.create({
                'schedule_id': self.schedule_id.id,
                'date': date,
                'reason': self.reason,
                'block_existing': self.block_existing,
            })
            created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success',
                       'message': _('%s off days added.') % created,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
