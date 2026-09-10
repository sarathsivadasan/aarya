# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class BookingPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'booking_count' in counters:
            values['booking_count'] = request.env[
                'odex.workshop.booking'].search_count(self._booking_domain())
        if 'vehicle_count' in counters:
            values['vehicle_count'] = request.env['fleet.vehicle'].sudo(
                ).search_count(self._vehicle_domain())
        return values

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _partner(self):
        return request.env.user.partner_id.commercial_partner_id

    def _owned_or_404(self, record, partner_field='partner_id'):
        """Ownership gate for every id that arrives from a URL.

        sudo() is only ever used AFTER this check passes, and only to read
        internal workshop data the customer is entitled to see. Changing an
        id in the address bar can never return another customer's record.
        """
        if not record or not record.exists():
            raise request.not_found()
        partner = self._partner()
        owner = record[partner_field] if partner_field in record._fields \
            else record.env['res.partner']
        allowed = {partner.id} | set(partner.child_ids.ids) | \
            {request.env.user.partner_id.id}
        if owner and owner.commercial_partner_id.id not in allowed \
                and owner.id not in allowed:
            raise request.not_found()
        return record

    def _vehicle_domain(self):
        partner = self._partner()
        return ['|', ('driver_id', 'child_of', partner.id),
                ('driver_id', '=', request.env.user.partner_id.id)]

    def _vehicles(self):
        return request.env['fleet.vehicle'].sudo().search(
            self._vehicle_domain(), order='license_plate, id')

    def _optional(self, record, field_names):
        """Read fields that only exist when other Odex modules are installed.

        The portal must render the same on a database with or without the
        workshop add-ons, so nothing here assumes a schema it does not own.
        """
        result = {}
        for name in field_names:
            field = record._fields.get(name)
            if not field:
                continue
            value = record[name]
            if not value:
                continue
            result[name] = value.display_name if field.type in (
                'many2one',) else value
        return result

    VEHICLE_OPTIONAL_FIELDS = [
        'fleet_emirate_id', 'fleet_code_id', 'engine_number', 'cylinder_count',
        'variant', 'variant_id', 'trim_id', 'fuel_type', 'transmission',
        'odometer', 'warranty_expiry', 'warranty_end_date',
        'registration_expiry', 'mulkiya_expiry', 'insurance_expiry',
        'insurance_end_date', 'last_service_date', 'next_service_date',
        'next_service_odometer', 'vehicle_status', 'state_id',
    ]

    def _vehicle_values(self, vehicle):
        return {
            'vehicle': vehicle,
            'extra': self._optional(vehicle, self.VEHICLE_OPTIONAL_FIELDS),
            'status': vehicle._service_status(),
        }

    def _sibling_model(self, candidates):
        """Return the first model that actually exists in this database."""
        for name in candidates:
            if name in request.env:
                return request.env[name].sudo()
        return None

    JOB_CARD_MODELS = ['job.card', 'garage.job.card', 'workshop.job.card',
                       'odex.job.card', 'fleet.job.card']

    def _job_cards(self, limit=None):
        model = self._sibling_model(self.JOB_CARD_MODELS)
        if not model:
            return None
        partner = self._partner()
        field = 'partner_id' if 'partner_id' in model._fields else None
        if not field:
            return None
        return model.search([(field, 'child_of', partner.id)],
                            limit=limit, order='id desc')

    def _invoices(self, limit=None):
        partner = self._partner()
        return request.env['account.move'].sudo().search([
            ('partner_id', 'child_of', partner.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
        ], limit=limit, order='invoice_date desc, id desc')

    def _quotations(self, limit=None):
        if 'sale.order' not in request.env:
            return None
        partner = self._partner()
        return request.env['sale.order'].sudo().search([
            ('partner_id', 'child_of', partner.id),
        ], limit=limit, order='date_order desc')

    def _booking_domain(self):
        partner = request.env.user.partner_id
        return [('partner_id', 'child_of', partner.commercial_partner_id.id)]

    def _get_booking(self, booking_id):
        booking = request.env['odex.workshop.booking'].sudo().browse(
            int(booking_id))
        return self._owned_or_404(booking)

    @http.route(['/my/bookings', '/my/bookings/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_bookings(self, page=1, filterby='upcoming', **kw):
        Booking = request.env['odex.workshop.booking']
        domain = self._booking_domain()
        today = fields.Date.today()
        filters = {
            'upcoming': {'label': _('Upcoming'), 'domain': [
                ('booking_date', '>=', today),
                ('state', 'in', ('draft', 'requested', 'confirmed', 'arrived'))]},
            'history': {'label': _('History'), 'domain': [
                '|', ('booking_date', '<', today),
                ('state', 'in', ('done', 'cancelled', 'no_show'))]},
            'all': {'label': _('All'), 'domain': []},
        }
        current = filters.get(filterby, filters['upcoming'])
        full_domain = domain + current['domain']
        total = Booking.search_count(full_domain)
        pager = portal_pager(
            url='/my/bookings', total=total, page=page, step=10,
            url_args={'filterby': filterby})
        bookings = Booking.search(
            full_domain, order='booking_date desc, hour_from desc',
            limit=10, offset=pager['offset'])
        return request.render('odex_workshop_booking.portal_my_bookings', {
            'bookings': bookings,
            'page_name': 'booking',
            'pager': pager,
            'filterby': filterby,
            'searchbar_filters': filters,
            'default_url': '/my/bookings',
        })

    def _booking_related(self, booking):
        """Job card / quotation / invoice linked to a booking, when the
        matching module is installed. All reads are scoped to the customer's
        own partner, never widened."""
        related = {'job_card': None, 'quotation': None, 'invoice': None}
        partner = self._partner()
        model = self._sibling_model(self.JOB_CARD_MODELS)
        if model and 'partner_id' in model._fields:
            domain = [('partner_id', 'child_of', partner.id)]
            if 'vehicle_id' in model._fields and booking.vehicle_id:
                domain.append(('vehicle_id', '=', booking.vehicle_id.id))
            related['job_card'] = model.search(domain, limit=1, order='id desc')
        quotations = self._quotations(limit=1)
        if quotations:
            related['quotation'] = quotations[:1]
        invoices = self._invoices(limit=1)
        if invoices:
            related['invoice'] = invoices[:1]
        return related

    @http.route('/my/bookings/<int:booking_id>', type='http', auth='user',
                website=True)
    def portal_booking_detail(self, booking_id, **kw):
        try:
            booking = self._get_booking(booking_id)
        except Exception:
            return request.redirect('/my/bookings')
        can_cancel, can_reschedule = self._booking_rights(booking)
        values = {
            'booking': booking,
            'page_name': 'booking',
            'can_cancel': can_cancel,
            'can_reschedule': can_reschedule,
        }
        values.update(self._booking_related(booking))
        return request.render(
            'odex_workshop_booking.portal_booking_detail', values)

    def _booking_rights(self, booking):
        if booking.state not in ('draft', 'requested', 'confirmed'):
            return False, False
        now = fields.Datetime.now()
        company = booking.company_id
        can_cancel = booking.start_datetime and booking.start_datetime > \
            now + timedelta(hours=company.cancel_limit_hours)
        can_reschedule = booking.start_datetime and booking.start_datetime > \
            now + timedelta(hours=company.reschedule_limit_hours)
        return can_cancel, can_reschedule

    @http.route('/my/bookings/<int:booking_id>/cancel', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_booking_cancel(self, booking_id, reason=None, **kw):
        try:
            booking = self._get_booking(booking_id)
        except Exception:
            return request.redirect('/my/bookings')
        can_cancel, _dummy = self._booking_rights(booking)
        if can_cancel:
            booking.sudo().action_cancel(
                reason=reason or _('Cancelled by customer from portal.'))
        return request.redirect('/my/bookings/%s' % booking.id)

    @http.route('/my/bookings/<int:booking_id>/reschedule', type='json',
                auth='user', website=True)
    def portal_booking_reschedule(self, booking_id, slot_id, reason=None, **kw):
        try:
            booking = self._get_booking(booking_id)
        except Exception:
            return {'error': _('Booking not found.')}
        _dummy, can_reschedule = self._booking_rights(booking)
        if not can_reschedule:
            return {'error': _('This booking can no longer be rescheduled.')}
        slot = request.env['odex.booking.slot'].sudo().browse(int(slot_id))
        if not slot.exists() or not slot._is_bookable():
            return {'error': _('The selected slot is no longer available.')}
        request.env['odex.booking.reschedule'].sudo().create({
            'booking_id': booking.id,
            'old_slot_id': booking.slot_id.id,
            'new_slot_id': slot.id,
            'reason': reason or False,
            'requested_by': 'customer',
        }).action_approve()
        return {'success': True}

    # Vehicles ----------------------------------------------------------
    @http.route('/my/vehicles', type='http', auth='user', website=True)
    def portal_my_vehicles(self, **kw):  # noqa: D401 - list view
        partner = request.env.user.partner_id
        vehicles = request.env['fleet.vehicle'].sudo().search([
            '|', ('driver_id', '=', partner.id),
            ('driver_id', 'child_of', partner.commercial_partner_id.id)])
        makes = request.env['fleet.vehicle.model.brand'].sudo().search([])
        plate_options = request.env['fleet.vehicle']._plate_options()
        return request.render('odex_workshop_booking.portal_my_vehicles', {
            **plate_options,
            'vehicles': vehicles,
            'vehicle_rows': [self._vehicle_values(v) for v in vehicles],
            'makes': makes,
            'page_name': 'vehicle',
        })

    @http.route('/my/vehicles/add', type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def portal_add_vehicle(self, **post):
        partner = request.env.user.partner_id
        model_id = post.get('model_id')
        if model_id:
            Vehicle = request.env['fleet.vehicle'].sudo()
            vals = {
                'model_id': int(model_id),
                'license_plate': post.get('plate') or False,
                'vin_sn': post.get('vin') or False,
                'model_year': post.get('year') or False,
                'color': post.get('color') or False,
            }
            Vehicle._apply_plate_values(
                vals, post.get('emirate_id'), post.get('code_id'))
            Vehicle._find_or_create_from_booking(partner, vals)
        return request.redirect('/my/vehicles')

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    # NOTE: the method MUST be named ``home`` — Odoo replaces a parent
    # controller route only when the subclass reuses the same method name.
    # A differently-named method on the same path leaves both endpoints
    # registered and Odoo keeps serving the original portal page.
    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        """Odex workshop dashboard — the portal landing page."""
        if not request.env.user.has_group('base.group_portal'):
            # Internal users keep the standard Odoo portal home.
            return super().home(**kw)
        partner = self._partner()
        vehicles = self._vehicles()
        job_cards = self._job_cards()
        quotations = self._quotations()
        Location = request.env['odex.booking.location']
        values = {
            'page_name': 'workshop_home',
            'partner': partner,
            'vehicle_rows': [self._vehicle_values(v) for v in vehicles[:5]],
            'vehicle_count': len(vehicles),
            'booking_count': request.env['odex.workshop.booking'].search_count(
                self._booking_domain()),
            'invoice_count': len(self._invoices()),
            'job_card_count': len(job_cards) if job_cards is not None else None,
            'quotation_count': len(quotations) if quotations is not None else None,
            'pickup_locations': Location._available('pickup'),
            'drop_locations': Location._available('drop'),
            'pickup_location': partner.booking_pickup_location_id,
            'drop_location': partner.booking_drop_location_id,
        }
        return request.render(
            'odex_workshop_booking.portal_workshop_home', values)

    @http.route('/my/workshop', type='http', auth='user', website=True)
    def portal_workshop_legacy(self, **kw):
        """Backward compatibility for the previous dashboard URL."""
        return request.redirect('/my')

    @http.route('/my/workshop/locations', type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def portal_set_locations(self, pickup_location_id=None,
                             drop_location_id=None, **kw):
        self._partner().sudo().write({
            'booking_pickup_location_id': int(pickup_location_id)
            if pickup_location_id else False,
            'booking_drop_location_id': int(drop_location_id)
            if drop_location_id else False,
        })
        return request.redirect('/my/workshop')

    # ------------------------------------------------------------------
    # Vehicles
    # ------------------------------------------------------------------
    @http.route('/my/vehicles/<int:vehicle_id>', type='http', auth='user',
                website=True)
    def portal_vehicle_detail(self, vehicle_id, **kw):
        vehicle = request.env['fleet.vehicle'].sudo().browse(vehicle_id)
        # Ownership first, sudo reads only afterwards.
        self._owned_or_404(vehicle, 'driver_id')
        bookings = request.env['odex.workshop.booking'].search(
            self._booking_domain() + [('vehicle_id', '=', vehicle.id)],
            order='booking_date desc', limit=10)
        invoices = self._invoices()
        values = self._vehicle_values(vehicle)
        values.update({
            'page_name': 'vehicle',
            'bookings': bookings,
            'invoices': invoices[:5],
            'timeline': vehicle._service_timeline(),
            'partner': self._partner(),
        })
        return request.render(
            'odex_workshop_booking.portal_vehicle_detail', values)

    # ------------------------------------------------------------------
    # Service history / support / documents
    # ------------------------------------------------------------------
    @http.route('/my/service-history', type='http', auth='user', website=True)
    def portal_service_history(self, **kw):
        invoices = self._invoices()
        return request.render(
            'odex_workshop_booking.portal_service_history', {
                'page_name': 'service_history',
                'invoices': invoices,
                'vehicles': self._vehicles(),
            })

    @http.route('/my/workshop/support', type='http', auth='user', website=True)
    def portal_support(self, **kw):
        partner = self._partner()
        company = request.env.company.sudo()
        return request.render('odex_workshop_booking.portal_support', {
            'page_name': 'support',
            'company': company,
            'location': partner.booking_drop_location_id,
            'locations': request.env['odex.booking.location']._available('drop'),
            'working_hours': company.working_hours_ids,
        })

    @http.route('/my/workshop/documents', type='http', auth='user',
                website=True)
    def portal_documents(self, **kw):
        vehicles = self._vehicles()
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'fleet.vehicle'),
            ('res_id', 'in', vehicles.ids),
        ], order='create_date desc')
        by_vehicle = {}
        for attachment in attachments:
            by_vehicle.setdefault(attachment.res_id, []).append(attachment)
        return request.render('odex_workshop_booking.portal_documents', {
            'page_name': 'documents',
            'vehicles': vehicles,
            'documents': by_vehicle,
        })

    @http.route('/my/quotations/<int:quotation_id>', type='http',
                auth='user', website=True)
    def portal_quotation_detail(self, quotation_id, **kw):
        """Hand off to Odoo's own quotation page.

        Reimplementing the sale portal page meant re-deriving Accept & Sign,
        the signature flow, the access token, the message thread, taxes and
        payment — all of which Odoo already does correctly. We validate
        ownership here, then redirect to the standard route with the record's
        own access token so portal security is Odoo's, not ours. The ODEX
        booking details are added to that page by an XPath inherit instead.
        """
        quote = request.env['sale.order'].sudo().browse(quotation_id)
        self._owned_or_404(quote)
        token = quote._portal_ensure_token() \
            if hasattr(quote, '_portal_ensure_token') else quote.access_token
        url = '/my/orders/%s' % quote.id
        if token:
            url += '?access_token=%s' % token
        return request.redirect(url)

    @http.route('/my/quotations', type='http', auth='user', website=True)
    def portal_quotations(self, **kw):
        """Quotation list. Redirects to Odoo's own page when sale is absent."""
        quotations = self._quotations()
        if quotations is None:
            return request.redirect('/my/workshop')
        return request.render('odex_workshop_booking.portal_quotations', {
            'page_name': 'quotation',
            'quotations': quotations,
        })
