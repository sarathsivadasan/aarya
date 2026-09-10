# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BookingReschedule(models.Model):
    _name = 'odex.booking.reschedule'
    _description = 'Booking Reschedule Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    booking_id = fields.Many2one(
        'odex.workshop.booking', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='booking_id.partner_id', store=True)
    company_id = fields.Many2one(related='booking_id.company_id', store=True)
    old_slot_id = fields.Many2one('odex.booking.slot', string='Current Slot')
    old_date = fields.Date(related='old_slot_id.date', string='Current Date')
    old_time = fields.Char(
        related='booking_id.time_label', string='Current Time')

    # Pick the date first, then the time — a flat dropdown of every slot in
    # the schedule is unusable once a few hundred exist.
    new_date = fields.Date(
        string='New Date', required=True,
        default=lambda self: fields.Date.context_today(self))
    new_slot_id = fields.Many2one(
        'odex.booking.slot', string='Existing Slot',
        domain="[('company_id', '=', company_id),"
               "('date', '=', new_date),"
               "('is_break', '=', False),"
               "('state', 'in', ('available', 'limited'))]")
    available_slot_ids = fields.Many2many(
        'odex.booking.slot', compute='_compute_available_slots',
        string='Free Times')
    slot_summary = fields.Char(compute='_compute_available_slots')
    reason = fields.Text()
    requested_by = fields.Selection([
        ('customer', 'Customer'),
        ('staff', 'Workshop Staff'),
    ], default='staff', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', tracking=True)

    new_hour = fields.Float(string='New Time', help='Free times are listed '
                            'below; they come straight from the schedule.')

    @api.depends('company_id', 'new_date')
    def _compute_available_slots(self):
        """Free times from the live engine, not from generated rows."""
        Availability = self.env['odex.booking.availability']
        for rec in self:
            rec.available_slot_ids = self.env['odex.booking.slot'].browse()
            if not (rec.company_id and rec.new_date):
                rec.slot_summary = ''
                continue
            rows = [r for r in Availability.day_slots(
                rec.company_id, rec.new_date, admin=True) if r['remaining'] > 0]
            rec.slot_summary = ', '.join(r['label'] for r in rows) \
                if rows else _('The workshop is closed or full on this date.')

    @api.onchange('new_date')
    def _onchange_new_date(self):
        """Drop a time that no longer belongs to the chosen date."""
        if self.new_slot_id and self.new_slot_id.date != self.new_date:
            self.new_slot_id = False

    @api.onchange('booking_id')
    def _onchange_booking(self):
        if self.booking_id:
            self.old_slot_id = self.booking_id.slot_id
            if self.booking_id.booking_date:
                self.new_date = self.booking_id.booking_date

    @api.constrains('new_slot_id', 'booking_id')
    def _check_new_slot(self):
        for rec in self:
            slot = rec.new_slot_id
            if not slot:
                continue
            if slot == rec.booking_id.slot_id:
                raise ValidationError(_(
                    'The new time is the same as the current one.'))
            if not slot._is_bookable():
                raise ValidationError(_(
                    'That time is no longer bookable. Please choose another.'))

    def _resolve_slot(self):
        """Materialise the chosen date+time into a real slot row."""
        self.ensure_one()
        if self.new_slot_id:
            return self.new_slot_id
        if not self.new_hour:
            raise UserError(_('Choose a time.'))
        return self.env['odex.booking.availability'].materialise(
            self.company_id, self.new_date, self.new_hour)

    def action_approve(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be approved.'))
            old = rec.booking_id.slot_id
            rec.booking_id._move_to_slot(rec._resolve_slot())
            rec.state = 'approved'
            rec.booking_id.message_post(body=_(
                'Rescheduled from %(old)s to %(new)s.',
                old=old.display_name or _('unscheduled'),
                new=rec.new_slot_id.display_name))
        return True

    def action_reject(self):
        self.filtered(lambda r: r.state == 'pending').write({'state': 'rejected'})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Staff-created requests apply immediately
        for rec in records.filtered(lambda r: r.requested_by == 'staff'):
            rec.action_approve()
        return records
