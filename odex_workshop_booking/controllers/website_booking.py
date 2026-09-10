# -*- coding: utf-8 -*-
import logging

from odoo import http, fields, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class WebsiteBooking(http.Controller):

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    @http.route('/book-service', type='http', auth='public', website=True,
                sitemap=True)
    def booking_page(self, **kw):
        env = request.env
        companies = env['res.company'].sudo().search(
            [('booking_published', '=', True)])
        services = env['odex.booking.service.type'].sudo().search(
            [('website_published', '=', True)])
        user = env.user
        partner = user.partner_id.commercial_partner_id \
            if not user._is_public() else env['res.partner']
        own_vehicles = env['fleet.vehicle'].sudo().search(
            ['|', ('driver_id', 'child_of', partner.id),
             ('driver_id', '=', user.partner_id.id)]) if partner else \
            env['fleet.vehicle']
        countries = env['res.country'].sudo().search([])
        makes = env['fleet.vehicle.model.brand'].sudo().search([])
        icp = env['ir.config_parameter'].sudo()
        return request.render('odex_workshop_booking.booking_wizard_page', {
            'companies': companies,
            **env['fleet.vehicle']._plate_options(),
            'pickup_locations': env['odex.booking.location']._available('pickup'),
            'drop_locations': env['odex.booking.location']._available('drop'),
            'portal_partner': partner,
            'own_vehicles': own_vehicles,
            'own_vehicle_status': {v.id: v._service_status()
                                   for v in own_vehicles},
            'pickup_location': partner.booking_pickup_location_id if partner else False,
            'drop_location': partner.booking_drop_location_id if partner else False,
            'services': services,
            'countries': countries,
            'makes': makes,
            'help_phone': icp.get_param('odex_workshop_booking.help_phone', ''),
            'terms_url': icp.get_param('odex_workshop_booking.terms_url', '#'),
            'default_country': env.ref('base.ae', raise_if_not_found=False),
        })

    @http.route('/booking/thank-you/<string:booking_ref>', type='http',
                auth='public', website=True, sitemap=False)
    def booking_thank_you(self, booking_ref, **kw):
        booking = request.env['odex.workshop.booking'].sudo().search(
            [('name', '=', booking_ref)], limit=1)
        if not booking:
            return request.redirect('/book-service')
        return request.render('odex_workshop_booking.booking_thank_you_page', {
            'booking': booking,
        })

    # ------------------------------------------------------------------
    # JSON API (also usable by future mobile apps)
    # ------------------------------------------------------------------
    def _get_company(self, company_id):
        """Resolve a company id coming from the public JS, tolerating an empty
        selector (nothing published yet / user cleared the field)."""
        Company = request.env['res.company'].sudo()
        try:
            company = Company.browse(int(company_id))
        except (TypeError, ValueError):
            company = Company.browse()
        if not company.exists():
            company = Company.search([('booking_published', '=', True)], limit=1)
        return company

    @http.route('/booking/api/month', type='json', auth='public', website=True)
    def api_month(self, company_id=None, year=None, month=None):
        company = self._get_company(company_id)
        if not company:
            return {'days': {}, 'error': 'no_company'}
        Slot = request.env['odex.booking.slot'].sudo()
        today = fields.Date.today()
        year = int(year or today.year)
        month = int(month or today.month)
        result = request.env['odex.booking.availability'].sudo(
            ).month_availability(company, year, month)
        days, reasons = result['days'], result['reasons']
        # Diagnostic: lets the customer (and the log) see *why* a month is
        # empty instead of showing a silently grey calendar.
        summary = {}
        for reason in reasons.values():
            summary[reason] = summary.get(reason, 0) + 1
        if not any(v in ('available', 'limited') for v in days.values()):
            _logger.info(
                'Booking calendar empty for company %s %s-%s: %s',
                company.name, year, month, summary)
        return {'days': days, 'reasons': reasons, 'summary': summary,
                'company_id': company.id}

    @http.route('/booking/api/slots', type='json', auth='public', website=True)
    def api_slots(self, company_id=None, date=None):
        company = self._get_company(company_id)
        if not company or not date:
            return {'slots': [], 'error': 'no_company'}
        d = fields.Date.to_date(date)
        Slot = request.env['odex.booking.slot'].sudo()
        return {'slots': request.env['odex.booking.availability'].sudo(
                ).day_slots(company, d),
                'tz': company.booking_tz,
                'duration': company.slot_duration}

    @http.route('/booking/api/customer_lookup', type='json', auth='public',
                website=True)
    def api_customer_lookup(self, mobile=None, phone=None, email=None):
        """Return whether a matching customer exists and their vehicles.
        Only non-sensitive data is exposed publicly."""
        Partner = request.env['res.partner'].sudo()
        terms = []
        for value in filter(None, [mobile, phone]):
            value = value.strip()
            terms.append(['|', ('mobile', '=ilike', value), ('phone', '=ilike', value)])
        if email:
            terms.append([('email', '=ilike', email.strip())])
        if not terms:
            return {'found': False}
        domain = ['|'] * (len(terms) - 1)
        for t in terms:
            domain += t
        partner = Partner.search(domain, limit=1)
        if not partner:
            return {'found': False}
        vehicles = request.env['fleet.vehicle'].sudo().search([
            '|', ('driver_id', '=', partner.id),
            ('driver_id', 'child_of', partner.id)])
        return {
            'found': True,
            'name': partner.name,
            'vehicles': [{
                'id': v.id,
                'name': v.display_name,
                'plate': v.license_plate or '',
                'model': v.model_id.name or '',
                'make': v.model_id.brand_id.name or '',
                'year': v.model_year or '',
            } for v in vehicles],
        }

    @http.route('/booking/api/models', type='json', auth='public', website=True)
    def api_models(self, brand_id=None):
        if not brand_id:
            return {'models': []}
        models = request.env['fleet.vehicle.model'].sudo().search(
            [('brand_id', '=', int(brand_id))])
        return {'models': [{'id': m.id, 'name': m.name} for m in models]}

    @http.route('/booking/api/submit', type='json', auth='public', website=True)
    def api_submit(self, **payload):
        env = request.env
        try:
            # The wizard now posts date + time, not a slot id: the row is
            # created on demand instead of pre-generated.
            company = self._get_company(payload.get('company_id'))
            slot = env['odex.booking.availability'].sudo().materialise(
                company,
                fields.Date.to_date(payload['date']),
                float(payload['hour_from']))
            if not slot.exists() or not slot._is_bookable():
                return {'error': _('The selected slot is no longer available. '
                                   'Please choose another time.')}
            service = env['odex.booking.service.type'].sudo().browse(
                int(payload['service_type_id']))
            if not service.exists():
                return {'error': _('Invalid service type.')}

            customer_vals = dict(payload.get('customer') or {})
            country_id = customer_vals.get('country_id')
            customer_vals['country_id'] = int(country_id) if country_id else False
            if not customer_vals.get('name') or not customer_vals.get('mobile'):
                return {'error': _('Name and mobile number are required.')}
            partner = env['res.partner'].sudo()._find_or_create_from_booking(
                customer_vals)

            vehicle_data = payload.get('vehicle') or {}
            if vehicle_data.get('id'):
                vehicle = env['fleet.vehicle'].sudo().browse(
                    int(vehicle_data['id']))
                if not vehicle.exists():
                    return {'error': _('Invalid vehicle.')}
            else:
                model_id = vehicle_data.get('model_id')
                if not model_id:
                    return {'error': _('Vehicle make and model are required.')}
                vals = {
                    'model_id': int(model_id),
                    'license_plate': vehicle_data.get('plate') or False,
                    'vin_sn': vehicle_data.get('vin') or False,
                    'model_year': vehicle_data.get('year') or False,
                    'color': vehicle_data.get('color') or False,

                    'engine_number': vehicle_data.get('engine_number') or False,
                    'cylinder_count': int(vehicle_data.get('cylinders') or 0),
                }
                # fleet.vehicle._set_odometer raises when the value is 0, so
                # only send it when the customer actually entered a reading.
                odometer = float(vehicle_data.get('odometer') or 0)
                if odometer > 0:
                    vals['odometer'] = odometer
                # Native fleet plate fields, resolved by name at runtime.
                request.env['fleet.vehicle']._apply_plate_values(
                    vals, vehicle_data.get('emirate_id'),
                    vehicle_data.get('code_id'))
                vehicle = env['fleet.vehicle'].sudo()._find_or_create_from_booking(
                    partner, vals)

            advisor_id = payload.get('advisor_id')
            booking = env['odex.workshop.booking'].sudo().create({
                'partner_id': partner.id,
                'vehicle_id': vehicle.id,
                'company_id': slot.company_id.id,
                'slot_id': slot.id,
                'service_type_id': service.id,
                'complaint': payload.get('complaint') or False,
                'referral_source': payload.get('referral_source') or False,
                'pickup_location_id': int(payload['pickup_location_id'])
                if payload.get('pickup_location_id') else False,
                'drop_location_id': int(payload['drop_location_id'])
                if payload.get('drop_location_id') else False,
                'customer_note': payload.get('note') or False,
                'mobile': customer_vals.get('mobile'),
                'phone': customer_vals.get('phone') or False,
                'email': customer_vals.get('email') or False,
                'country_id': int(customer_vals.get('country_id') or 0) or False,
                'advisor_id': int(advisor_id) if advisor_id else False,
                'source': 'website',
                'state': 'requested',
            })
            auto_confirm = env['ir.config_parameter'].sudo().get_param(
                'odex_workshop_booking.auto_confirm')
            if auto_confirm:
                booking.action_confirm()
            else:
                booking._create_calendar_event()
                booking._send_template('mail_template_booking_confirmation')
            return {
                'success': True,
                'booking_ref': booking.name,
                'redirect': '/booking/thank-you/%s' % booking.name,
            }
        except (KeyError, ValueError, TypeError):
            _logger.warning('Booking submit: bad payload %s', payload,
                            exc_info=True)
            return {'error': _('Invalid booking data. Please check the form '
                               'and try again.')}
        except (UserError, ValidationError) as error:
            # Business rules (capacity, duplicate vehicle, ...) — show the
            # real reason instead of a generic failure.
            request.env.cr.rollback()
            return {'error': error.args[0] if error.args else _(
                'The booking could not be saved.')}
        except AccessError:
            request.env.cr.rollback()
            _logger.exception('Booking submit: access error')
            return {'error': _('The booking could not be saved. Please '
                               'contact the workshop.')}
        except Exception:
            # Anything else (mail server down, calendar, database) must not
            # surface as an opaque 500 to the customer.
            request.env.cr.rollback()
            _logger.exception('Booking submit failed for payload %s', payload)
            return {'error': _('We could not complete your booking. Please '
                               'try again or contact the workshop.')}
