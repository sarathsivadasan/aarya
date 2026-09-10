# -*- coding: utf-8 -*-
from datetime import timedelta

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WorkshopBooking(models.Model):
    _name = 'odex.workshop.booking'
    _description = 'Workshop Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'booking_date desc, hour_from desc, id desc'

    name = fields.Char(
        string='Booking Number', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], default='draft', tracking=True, index=True, copy=False)
    referral_source = fields.Selection([
        ('friend', 'Friend / Family'),
        ('google', 'Google Search'),
        ('social', 'Social Media'),
        ('repeat', 'Existing Customer'),
        ('passing', 'Passing By'),
        ('other', 'Other'),
    ], string='How did you hear about us?', tracking=True, index=True)
    source = fields.Selection([
        ('website', 'Website'),
        ('portal', 'Portal'),
        ('phone', 'Phone'),
        ('walkin', 'Walk-in'),
        ('internal', 'Internal'),
    ], default='internal', tracking=True)
    color = fields.Integer(compute='_compute_color')

    # Pickup / drop-off ------------------------------------------------
    pickup_location_id = fields.Many2one(
        'odex.booking.location', string='Pickup Location',
        domain="[('location_type', 'in', ('both', 'pickup'))]")
    drop_location_id = fields.Many2one(
        'odex.booking.location', string='Drop-off Location',
        domain="[('location_type', 'in', ('both', 'drop'))]")

    # Service progress mirrored from the job card ----------------------
    service_status = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('received', 'Vehicle Received'),
        ('inspection', 'Inspection'),
        ('estimate_sent', 'Estimate Sent'),
        ('estimate_approved', 'Estimate Approved'),
        ('in_progress', 'Work In Progress'),
        ('waiting_parts', 'Waiting Parts'),
        ('ready', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ], string='Service Status', compute='_compute_service_status',
        store=True, readonly=False, tracking=True,
        help='Derived from the booking state and kept in sync with the job '
             'card stage when a job card module is installed.')
    payment_status = fields.Selection([
        ('not_invoiced', 'Not Invoiced'),
        ('to_pay', 'To Pay'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string='Payment Status', default='not_invoiced', tracking=True)

    # Customer
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True, index=True)
    partner_name = fields.Char(related='partner_id.name', string='Customer Name')
    mobile = fields.Char(tracking=True)
    phone = fields.Char()
    email = fields.Char()
    country_id = fields.Many2one('res.country', string='Country')

    # Vehicle
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, tracking=True, index=True)
    vehicle_plate = fields.Char(
        related='vehicle_id.license_plate', string='Plate Number', store=True)
    vehicle_plate_label = fields.Char(
        compute='_compute_vehicle_plate_label', string='Plate',
        help='Emirate / Code / Number as configured on the vehicle.')
    vehicle_vin = fields.Char(related='vehicle_id.vin_sn', string='VIN')

    # Schedule
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, tracking=True,
        index=True, default=lambda self: self.env.company)
    slot_id = fields.Many2one(
        'odex.booking.slot', string='Time Slot', required=True,
        tracking=True, index=True, ondelete='restrict')
    pick_date = fields.Date(
        string='Date', compute='_compute_pick', inverse='_inverse_pick',
        store=False,
        help='Change the appointment date directly. The matching time slot '
             'is resolved from the working schedule.')
    pick_hour = fields.Float(
        string='Time', compute='_compute_pick', inverse='_inverse_pick',
        store=False)
    available_time_ids = fields.Many2many(
        'odex.booking.slot', compute='_compute_pick', string='Free Times')

    booking_date = fields.Date(
        related='slot_id.date', store=True, string='Date', index=True)
    hour_from = fields.Float(related='slot_id.hour_from', store=True, string='Time')
    hour_to = fields.Float(related='slot_id.hour_to', store=True)
    start_datetime = fields.Datetime(
        related='slot_id.start_datetime', store=True, string='Start')
    stop_datetime = fields.Datetime(
        related='slot_id.stop_datetime', store=True, string='End')
    time_label = fields.Char(compute='_compute_time_label', string='Time Slot Label')

    # Service
    service_type_id = fields.Many2one(
        'odex.booking.service.type', string='Service Type', required=True, tracking=True)
    complaint = fields.Text(string='Vehicle Complaint')
    advisor_id = fields.Many2one(
        'res.users', string='Service Advisor', tracking=True,
        domain=lambda self: [('groups_id', 'in',
                              self.env.ref('odex_workshop_booking.group_booking_user').ids)])
    note = fields.Html(string='Internal Notes')
    customer_note = fields.Text(string='Customer Notes')

    calendar_event_id = fields.Many2one(
        'calendar.event', string='Calendar Event', copy=False)
    reminder_sent = fields.Boolean(copy=False)
    cancel_reason = fields.Text(copy=False)
    reschedule_count = fields.Integer(compute='_compute_reschedule_count')

    _sql_constraints = [
        ('vehicle_slot_unique',
         "unique(vehicle_id, slot_id)",
         'This vehicle already has a booking in the selected time slot.'),
    ]

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
    def _compute_color(self):
        colors = {'draft': 0, 'requested': 3, 'confirmed': 10,
                  'arrived': 4, 'done': 8, 'cancelled': 1, 'no_show': 2}
        for rec in self:
            rec.color = colors.get(rec.state, 0)

    def _compute_time_label(self):
        for rec in self:
            if rec.slot_id:
                h1, m1 = int(rec.hour_from), int(round((rec.hour_from % 1) * 60))
                h2, m2 = int(rec.hour_to), int(round((rec.hour_to % 1) * 60))
                rec.time_label = '%02d:%02d - %02d:%02d' % (h1, m1, h2, m2)
            else:
                rec.time_label = False

    def _compute_reschedule_count(self):
        data = dict(self.env['odex.booking.reschedule']._read_group(
            [('booking_id', 'in', self.ids)], ['booking_id'], ['__count']))
        for rec in self:
            rec.reschedule_count = data.get(rec, 0)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/bookings/%s' % rec.id

    @api.constrains('slot_id', 'state')
    def _check_capacity(self):
        for rec in self:
            if rec.state in ('cancelled', 'no_show'):
                continue
            slot = rec.slot_id
            active = slot.booking_ids.filtered(lambda b: b.id != rec.id)
            if not slot.allow_overbooking and len(active) >= slot.capacity:
                raise ValidationError(_(
                    'Slot %s is fully booked. Please choose another slot.',
                    slot.display_name))
            if slot.is_blocked:
                raise ValidationError(_('Slot %s is blocked.', slot.display_name))

    @api.constrains('vehicle_id', 'booking_date', 'state')
    def _check_vehicle_double_booking(self):
        for rec in self:
            if rec.state in ('cancelled', 'no_show', 'done'):
                continue
            duplicate = self.search_count([
                ('id', '!=', rec.id),
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('booking_date', '=', rec.booking_date),
                ('state', 'in', ('draft', 'requested', 'confirmed', 'arrived')),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Vehicle %s already has an active booking on %s.',
                    rec.vehicle_id.display_name, rec.booking_date))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.mobile = self.partner_id.mobile
            self.phone = self.partner_id.phone
            self.email = self.partner_id.email
            self.country_id = self.partner_id.country_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id and self.slot_id.company_id != self.company_id:
            self.slot_id = False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.workshop.booking') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancelled') for rec in self):
            raise UserError(_('Only draft or cancelled bookings can be deleted.'))
        self.mapped('calendar_event_id').unlink()
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_request(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'requested'})

    def action_confirm(self):
        for rec in self:
            if rec.state not in ('draft', 'requested'):
                raise UserError(_('Only draft/requested bookings can be confirmed.'))
            if not rec.slot_id._is_bookable() and rec.state == 'draft':
                # allow confirming a requested booking that already holds the seat
                pass
            rec.state = 'confirmed'
            rec._create_calendar_event()
            rec._send_template('mail_template_booking_confirmation')
        return True

    def action_mark_arrived(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Only confirmed bookings can be marked as arrived.'))
            rec.state = 'arrived'

    def action_complete(self):
        for rec in self:
            if rec.state != 'arrived':
                raise UserError(_('Only arrived bookings can be completed.'))
            rec.state = 'done'

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise UserError(_('This booking can no longer be cancelled.'))
            rec.write({'state': 'cancelled', 'cancel_reason': reason or rec.cancel_reason})
            if rec.calendar_event_id:
                rec.calendar_event_id.sudo().unlink()
            rec._send_template('mail_template_booking_cancelled')
        return True

    def action_no_show(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Only confirmed bookings can be marked as no-show.'))
            rec.state = 'no_show'
            if rec.calendar_event_id:
                rec.calendar_event_id.sudo().unlink()

    def action_reset_draft(self):
        self.filtered(lambda r: r.state in ('cancelled', 'no_show')).write(
            {'state': 'draft'})

    def action_open_reschedule(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reschedule Booking'),
            'res_model': 'odex.booking.reschedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
                'default_old_slot_id': self.slot_id.id,
                'default_new_date': self.booking_date or fields.Date.today(),
                'default_requested_by': 'staff',
            },
        }

    def action_open_calendar_event(self):
        self.ensure_one()
        if not self.calendar_event_id:
            raise UserError(_('No calendar event linked.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'res_id': self.calendar_event_id.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_calendar_event(self):
        """Best effort: a calendar failure must not cancel the booking."""
        self.ensure_one()
        try:
            return self._do_create_calendar_event()
        except Exception:
            _logger.warning('Booking %s: calendar event failed', self.name,
                            exc_info=True)
            return self.env['calendar.event']

    def _do_create_calendar_event(self):
        self.ensure_one()
        if self.calendar_event_id:
            self.calendar_event_id.sudo().write({
                'start': self.start_datetime, 'stop': self.stop_datetime})
            return self.calendar_event_id
        partner_ids = [self.partner_id.id]
        if self.advisor_id.partner_id:
            partner_ids.append(self.advisor_id.partner_id.id)
        event = self.env['calendar.event'].sudo().create({
            'name': '%s - %s (%s)' % (
                self.name, self.partner_id.name, self.vehicle_id.display_name),
            'start': self.start_datetime,
            'stop': self.stop_datetime,
            'partner_ids': [(6, 0, partner_ids)],
            'user_id': self.advisor_id.id or self.env.user.id,
            'description': _(
                'Service: %(service)s\nWorkshop: %(company)s\nComplaint: %(complaint)s',
                service=self.service_type_id.name,
                company=self.company_id.name,
                complaint=self.complaint or '-'),
            'res_model_id': self.env['ir.model']._get_id('odex.workshop.booking'),
            'res_id': self.id,
        })
        self.calendar_event_id = event
        return event

    def _send_template(self, xmlid):
        """Queue a notification. Never let mail problems break a booking:
        a missing or misconfigured outgoing mail server must not roll back the
        customer's appointment."""
        template = self.env.ref(
            'odex_workshop_booking.%s' % xmlid, raise_if_not_found=False)
        if not template:
            return
        for rec in self.filtered(lambda r: r.email or r.partner_id.email):
            try:
                template.sudo().send_mail(rec.id, force_send=False)
            except Exception:
                _logger.warning(
                    'Booking %s: could not queue mail template %s',
                    rec.name, xmlid, exc_info=True)

    def _move_to_slot(self, new_slot):
        """Reschedule core: release old slot, take new one, sync calendar."""
        self.ensure_one()
        if not new_slot._is_bookable():
            raise UserError(_('The selected slot is no longer available.'))
        self.write({'slot_id': new_slot.id,
                    'company_id': new_slot.company_id.id})
        if self.calendar_event_id:
            self.calendar_event_id.sudo().write({
                'start': new_slot.start_datetime, 'stop': new_slot.stop_datetime})
        self._send_template('mail_template_booking_rescheduled')

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_send_reminders(self):
        tomorrow = fields.Date.today() + timedelta(days=1)
        bookings = self.search([
            ('state', '=', 'confirmed'),
            ('booking_date', '=', tomorrow),
            ('reminder_sent', '=', False),
        ])
        for rec in bookings:
            rec._send_template('mail_template_booking_reminder')
            rec.reminder_sent = True

    @api.model
    def _cron_mark_no_show(self):
        """Auto no-show confirmed bookings whose slot ended yesterday or earlier."""
        cutoff = fields.Datetime.now() - timedelta(hours=12)
        self.search([
            ('state', '=', 'confirmed'),
            ('stop_datetime', '<', cutoff),
        ]).write({'state': 'no_show'})

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.depends('slot_id')
    def _compute_pick(self):
        for rec in self:
            rec.pick_date = rec.slot_id.date or rec.booking_date
            rec.pick_hour = rec.slot_id.hour_from or 0.0
            rec.available_time_ids = rec.slot_id

    def _inverse_pick(self):
        """Move the booking when staff edit the date or time inline."""
        Availability = self.env['odex.booking.availability']
        for rec in self:
            if not (rec.pick_date and rec.company_id):
                continue
            hour = rec.pick_hour or (rec.slot_id.hour_from or 0.0)
            if rec.slot_id and rec.slot_id.date == rec.pick_date \
                    and abs(rec.slot_id.hour_from - hour) < 0.0001:
                continue
            slot = Availability.materialise(rec.company_id, rec.pick_date, hour)
            rec._move_to_slot(slot)

    @api.depends('vehicle_id')
    def _compute_vehicle_plate_label(self):
        for rec in self:
            rec.vehicle_plate_label = rec.vehicle_id.plate_label() \
                if rec.vehicle_id else ''

    @api.depends('state')
    def _compute_service_status(self):
        """Baseline mapping from the booking workflow.

        A job card module can override this by writing ``service_status``
        directly — the field is stored and editable, so the sync stays
        one-directional and never fights an external writer.
        """
        mapping = {
            'draft': 'pending', 'requested': 'pending',
            'confirmed': 'confirmed', 'arrived': 'received',
            'done': 'delivered', 'cancelled': 'cancelled',
            'no_show': 'cancelled',
        }
        for rec in self:
            if rec.service_status in (
                    'inspection', 'estimate_sent', 'estimate_approved',
                    'in_progress', 'waiting_parts', 'ready') \
                    and rec.state == 'arrived':
                continue  # a job card is driving it; leave it alone
            rec.service_status = mapping.get(rec.state, 'pending')

    @api.model
    def _dashboard_base(self, company_id=None):
        domain = [('company_id', 'in', self.env.companies.ids)]
        if company_id:
            domain = [('company_id', '=', int(company_id))]
        return domain

    # ------------------------------------------------------------------
    # ONE definition of every dashboard KPI. The counter and the list you
    # get when clicking the card are produced from the same domain, so they
    # can never disagree.
    # ------------------------------------------------------------------
    @api.model
    def _kpi_domains(self, company_id=None):
        month_start = fields.Date.today().replace(day=1)
        base = self._dashboard_base(company_id) + [
            ('booking_date', '>=', month_start)]
        return {
            'total': base,
            'confirmed': base + [('state', '=', 'confirmed')],
            'pending': base + [('state', 'in', ('draft', 'requested'))],
            'arrived': base + [('state', '=', 'arrived')],
            'cancelled': base + [('state', 'in', ('cancelled', 'no_show'))],
            'done': base + [('state', '=', 'done')],
        }

    @api.model
    def get_dashboard_data(self, year=None, month=None, day=None,
                           company_id=None):
        """Everything the admin dashboard needs in a single round trip."""
        today = fields.Date.today()
        domains = self._kpi_domains(company_id)
        counts = {key: self.search_count(domain)
                  for key, domain in domains.items()}
        month_total = counts['total']

        def pct(value):
            return round(value * 100.0 / month_total) if month_total else 0

        base = self._dashboard_base(company_id)

        def count(domain):
            return self.search_count(base + domain)

        kpis = {
            'month_total': month_total,
            'confirmed': counts['confirmed'], 'confirmed_pct': pct(counts['confirmed']),
            'pending': counts['pending'], 'pending_pct': pct(counts['pending']),
            'arrived': counts['arrived'], 'arrived_pct': pct(counts['arrived']),
            'cancelled': counts['cancelled'], 'cancelled_pct': pct(counts['cancelled']),
            'done': counts['done'], 'done_pct': pct(counts['done']),
            'today': count([('booking_date', '=', today),
                            ('state', 'not in', ('cancelled', 'no_show'))]),
        }
        month_domain = [('booking_date', '>=', today.replace(day=1))]

        # Calendar overview -------------------------------------------------
        year = int(year or today.year)
        month = int(month or today.month)
        company = self.env['res.company'].browse(int(company_id)) \
            if company_id else self.env.company
        calendar = {}
        if company:
            calendar = self.env['odex.booking.availability'].month_availability(
                company, year, month, admin=True)['days']

        # Status donut -------------------------------------------------------
        status_data = self._read_group(
            base + month_domain, ['state'], ['__count'])
        labels = dict(self._fields['state'].selection)
        status = [{'label': labels.get(st, st), 'state': st, 'value': c,
                   'pct': pct(c)} for st, c in status_data]

        # Secondary analytics -----------------------------------------------
        daily = []
        for i in range(13, -1, -1):
            date = today - timedelta(days=i)
            daily.append({'label': date.strftime('%d %b'),
                          'value': count([
                              ('booking_date', '=', date),
                              ('state', 'not in', ('cancelled', 'no_show'))])})

        referral_data = self._read_group(
            base + month_domain, ['referral_source'], ['__count'])
        referral_labels = dict(self._fields['referral_source'].selection)
        palette = {
            'google': '#4285f4', 'social': '#e1306c', 'friend': '#16a34a',
            'repeat': '#7c3aed', 'passing': '#f59e0b', 'other': '#64748b',
        }
        acquisition = [{
            'key': key or 'unknown',
            'label': referral_labels.get(key, _('Not Specified')),
            'value': count,
            'color': palette.get(key, '#94a3b8'),
        } for key, count in referral_data]
        acquisition.sort(key=lambda item: item['value'], reverse=True)

        service_data = self._read_group(
            base + month_domain, ['service_type_id'], ['__count'],
            order='__count desc')
        services = [{'label': s.name if s else _('Undefined'), 'value': c}
                    for s, c in service_data[:6]]

        return {
            'kpis': kpis,
            'calendar': calendar,
            'calendar_year': year,
            'calendar_month': month,
            'status': status,
            'daily': daily,
            'acquisition': acquisition,
            'services': services,
            'company_id': company.id if company else False,
            'companies': [{'id': c.id, 'name': c.name}
                          for c in self.env.companies],
            'day_slots': self._admin_day_slots(
                company, day or fields.Date.to_string(today)),
            'selected_day': day or fields.Date.to_string(today),
        }

    @api.model
    def _admin_day_slots(self, company, day):
        """Slot panel rows for the dashboard, from the live engine."""
        if not company:
            return {'slots': [], 'booked': 0, 'capacity': 0}
        rows = self.env['odex.booking.availability'].day_slots(
            company, fields.Date.to_date(day), admin=True)
        labels = {'available': _('Available'), 'limited': _('Limited'),
                  'full': _('Fully Booked'), 'blocked': _('Blocked')}
        return {
            'slots': [{
                'id': '%s_%s' % (row['date'], row['hour_from']),
                'date': row['date'],
                'hour_from': row['hour_from'],
                'label': '%s - %s' % (row['label'], row['label_to']),
                'capacity': row['capacity'],
                'booked': row['booked'],
                'state': row['state'],
                'state_label': labels.get(row['state'], ''),
                'is_blocked': row['state'] == 'blocked',
                'is_break': False,
            } for row in rows],
            'booked': sum(r['booked'] for r in rows),
            'capacity': sum(r['capacity'] for r in rows),
        }

    @api.model
    def get_dashboard_bookings(self, offset=0, limit=10, search=None,
                               state=None, company_id=None, date=None,
                               kpi=None):
        """Paginated booking table for the dashboard."""
        if kpi:
            # Same domain that produced the number on the card.
            domain = list(self._kpi_domains(company_id).get(kpi, []))
        else:
            domain = self._dashboard_base(company_id)
        if state:
            domain.append(('state', '=', state))
        if date:
            domain.append(('booking_date', '=', date))
        if search:
            domain += ['|', '|', '|',
                       ('name', 'ilike', search),
                       ('partner_name', 'ilike', search),
                       ('vehicle_plate', 'ilike', search),
                       ('partner_id.mobile', 'ilike', search)]
        total = self.search_count(domain)
        records = self.search_read(
            domain, ['name', 'booking_date', 'time_label', 'partner_name',
                     'vehicle_id', 'service_type_id', 'state', 'source',
                     'referral_source', 'service_status', 'payment_status',
                     'advisor_id'],
            offset=int(offset), limit=int(limit),
            order='booking_date desc, hour_from')
        labels = dict(self._fields['state'].selection)
        source_labels = dict(self._fields['source'].selection)
        referral_labels = dict(self._fields['referral_source'].selection)
        service_labels = dict(self._fields['service_status'].selection)
        vehicle_ids = [r['vehicle_id'][0] for r in records if r['vehicle_id']]
        plate_by_id = {
            v.id: v.plate_label()
            for v in self.env['fleet.vehicle'].browse(vehicle_ids)
        }
        for rec in records:
            rec['booking_date'] = fields.Date.to_string(rec['booking_date'])
            rec['state_label'] = labels.get(rec['state'], rec['state'])
            rec['source_label'] = source_labels.get(rec['source'], '')
            rec['vehicle_name'] = rec['vehicle_id'][1] if rec['vehicle_id'] else ''
            rec['plate'] = plate_by_id.get(
                rec['vehicle_id'][0] if rec['vehicle_id'] else 0, '')
            rec['service_name'] = rec['service_type_id'][1] \
                if rec['service_type_id'] else ''
            rec['advisor_name'] = rec['advisor_id'][1] if rec['advisor_id'] else ''
            rec['referral_label'] = referral_labels.get(
                rec['referral_source'], '')
            rec['service_status_label'] = service_labels.get(
                rec['service_status'], '')
        return {'records': records, 'total': total}

    @api.model
    def get_booking_detail(self, booking_id):
        """Right-hand details panel."""
        booking = self.browse(int(booking_id))
        booking.check_access('read')
        labels = dict(self._fields['state'].selection)
        source_labels = dict(self._fields['source'].selection)
        plate_parts = booking.vehicle_id._plate_parts() \
            if booking.vehicle_id else ('', '', '')
        return {
            'id': booking.id,
            'name': booking.name,
            'state': booking.state,
            'state_label': labels.get(booking.state, booking.state),
            'partner_name': booking.partner_name or booking.partner_id.name,
            'mobile': booking.partner_id.mobile or booking.partner_id.phone or '',
            'email': booking.partner_id.email or '',
            'booking_date': fields.Date.to_string(booking.booking_date),
            'time_label': booking.time_label or '',
            'slot_id': booking.slot_id.id,
            'vehicle': booking.vehicle_id.display_name or '',
            'plate': booking.vehicle_id.plate_label()
            if booking.vehicle_id else '',
            'emirate': plate_parts[0],
            'plate_code': plate_parts[1],
            'plate_number': plate_parts[2],
            'vin': booking.vehicle_id.vin_sn or '',
            'make': booking.vehicle_id.model_id.brand_id.name or '',
            'model': booking.vehicle_id.model_id.name or '',
            'year': booking.vehicle_id.model_year or '',
            'color': booking.vehicle_id.color or '',
            'note': booking.note or '',
            'service': booking.service_type_id.name or '',
            'complaint': booking.complaint or '',
            'source': source_labels.get(booking.source, ''),
            'referral': dict(self._fields['referral_source'].selection).get(
                booking.referral_source, ''),
            'advisor': booking.advisor_id.name or '',
            'company': booking.company_id.name or '',
            'pickup': booking.pickup_location_id.display_name or '',
            'drop': booking.drop_location_id.display_name or '',
            'service_status': dict(
                self._fields['service_status'].selection).get(
                    booking.service_status, ''),
            'create_date': fields.Datetime.to_string(booking.create_date),
        }

    @api.model
    def dashboard_action(self, booking_id, action):
        """Run a workflow button from the dashboard details panel."""
        booking = self.browse(int(booking_id))
        method = {
            'arrived': 'action_mark_arrived',
            'complete': 'action_complete',
            'cancel': 'action_cancel',
            'confirm': 'action_confirm',
            'no_show': 'action_no_show',
        }.get(action)
        if not method:
            raise UserError(_('Unknown action.'))
        getattr(booking, method)()
        return self.get_booking_detail(booking.id)

    @api.model
    def open_kpi_action(self, kpi, company_id=None):
        """Open the booking list using the *same* domain the card counted."""
        domain = self._kpi_domains(company_id).get(kpi)
        if domain is None:
            domain = self._dashboard_base(company_id)
        labels = {'total': _('Total Bookings'), 'confirmed': _('Confirmed'),
                  'pending': _('Pending'), 'arrived': _('Arrived'),
                  'cancelled': _('Cancelled'), 'done': _('Completed')}
        return {
            'type': 'ir.actions.act_window',
            'name': labels.get(kpi, _('Bookings')),
            'res_model': 'odex.workshop.booking',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'target': 'current',
        }
