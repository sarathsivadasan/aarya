# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    booking_pickup_location_id = fields.Many2one(
        'odex.booking.location', string='Preferred Pickup Location',
        domain="[('location_type', 'in', ('both', 'pickup'))]")
    booking_drop_location_id = fields.Many2one(
        'odex.booking.location', string='Preferred Drop-off Location',
        domain="[('location_type', 'in', ('both', 'drop'))]")

    workshop_booking_ids = fields.One2many(
        'odex.workshop.booking', 'partner_id', string='Workshop Bookings')
    workshop_booking_count = fields.Integer(compute='_compute_booking_count')
    workshop_vehicle_ids = fields.One2many(
        'fleet.vehicle', 'driver_id', string='Vehicles')
    workshop_vehicle_count = fields.Integer(compute='_compute_vehicle_count')

    def _compute_booking_count(self):
        data = dict(self.env['odex.workshop.booking']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for rec in self:
            rec.workshop_booking_count = data.get(rec, 0)

    def _compute_vehicle_count(self):
        data = dict(self.env['fleet.vehicle']._read_group(
            [('driver_id', 'in', self.ids)], ['driver_id'], ['__count']))
        for rec in self:
            rec.workshop_vehicle_count = data.get(rec, 0)

    def action_view_workshop_bookings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'odex_workshop_booking.action_workshop_booking')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action

    @api.model
    def _find_or_create_from_booking(self, vals):
        """Match by mobile / phone / email; create only if no match."""
        mobile = (vals.get('mobile') or '').strip()
        phone = (vals.get('phone') or '').strip()
        email = (vals.get('email') or '').strip().lower()
        domain = []
        terms = []
        if mobile:
            terms.append(['|', ('mobile', '=ilike', mobile), ('phone', '=ilike', mobile)])
        if phone:
            terms.append(['|', ('mobile', '=ilike', phone), ('phone', '=ilike', phone)])
        if email:
            terms.append([('email', '=ilike', email)])
        if terms:
            domain = ['|'] * (len(terms) - 1)
            for t in terms:
                domain += t
            partner = self.search(domain, limit=1)
            if partner:
                update = {}
                if email and not partner.email:
                    update['email'] = email
                if mobile and not partner.mobile:
                    update['mobile'] = mobile
                if update:
                    partner.write(update)
                return partner
        return self.create({
            'name': vals.get('name'),
            'mobile': mobile or False,
            'phone': phone or False,
            'email': email or False,
            'country_id': vals.get('country_id') or False,
            'company_type': 'person',
        })
