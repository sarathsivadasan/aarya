# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    """The company IS the workshop branch — no separate branch model."""
    _inherit = 'res.company'

    booking_tz = fields.Selection(
        selection=lambda self: [(tz, tz) for tz in
                                self.env['res.partner']._fields['tz'].get_values(self.env)],
        string='Booking Timezone', default='Asia/Dubai', required=True)
    booking_published = fields.Boolean(
        string='Visible on Website', default=True,
        help='Offer this company as a bookable location on the website.')

    # Slot configuration
    slot_duration = fields.Float(
        string='Slot Duration (Hours)', default=0.5,
        help='Duration of each booking slot, e.g. 0.5 = 30 minutes.')
    slot_capacity = fields.Integer(
        string='Vehicles per Slot', default=3,
        help='Maximum vehicles that can be booked in one time slot.')
    max_advisors_per_slot = fields.Integer(string='Advisors per Slot', default=3)
    max_bookings_per_day = fields.Integer(
        string='Max Bookings per Day', default=0,
        help='0 = unlimited (slot capacity still applies).')

    # Booking rules
    min_notice_hours = fields.Integer(
        string='Minimum Notice (Hours)', default=0,
        help='Lead time customers must leave before an appointment.\n'
             '0 = any time still in the future can be booked, including '
             'later today. Past times are always blocked regardless.')
    max_advance_days = fields.Integer(
        string='Booking Window (Days)', default=30,
        help='How far in the future customers can book.')
    cancel_limit_hours = fields.Integer(
        string='Cancellation Limit (Hours)', default=4,
        help='Portal customers can cancel until this many hours before the slot.')
    reschedule_limit_hours = fields.Integer(
        string='Reschedule Limit (Hours)', default=4,
        help='Portal customers can reschedule until this many hours before the slot.')

    working_hours_ids = fields.One2many(
        'odex.booking.working.hours', 'company_id', string='Working Hours')
    advisor_ids = fields.Many2many(
        'res.users', 'odex_booking_company_advisor_rel', 'company_id', 'user_id',
        string='Service Advisors')

    slot_count = fields.Integer(compute='_compute_booking_counts')
    booking_count = fields.Integer(compute='_compute_booking_counts')

    def _compute_booking_counts(self):
        booking_data = dict(self.env['odex.workshop.booking']._read_group(
            [('company_id', 'in', self.ids)], ['company_id'], ['__count']))
        for rec in self:
            rec.slot_count = 0
            rec.booking_count = booking_data.get(rec, 0)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_slots(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_workshop_booking.action_booking_slot')
        action['domain'] = [('company_id', '=', self.id)]
        action['context'] = {'default_company_id': self.id}
        return action

    def action_view_bookings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_workshop_booking.action_workshop_booking')
        action['domain'] = [('company_id', '=', self.id)]
        action['context'] = {'default_company_id': self.id}
        return action

    def action_open_schedule(self):
        """Open (creating if needed) the working schedule of this company."""
        self.ensure_one()
        Schedule = self.env['odex.booking.schedule']
        schedule = Schedule.search([('company_id', '=', self.id)], limit=1)
        if not schedule:
            schedule = Schedule.create({
                'company_id': self.id,
                'default_capacity': self.slot_capacity or 3,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': schedule.name,
            'res_model': 'odex.booking.schedule',
            'res_id': schedule.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def _booking_companies(self):
        """Companies offered to website visitors."""
        return self.sudo().search([('booking_published', '=', True)])
