# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BookingLocation(models.Model):
    """Admin-configurable pickup / drop-off point.

    Deliberately independent of ``res.branch``: a location is a physical
    address a customer can hand over or collect a vehicle at, which is not
    the same concept as the accounting/scheduling branch.
    """
    _name = 'odex.booking.location'
    _description = 'Booking Pickup / Drop Location'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Char(string='Reference')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    location_type = fields.Selection([
        ('both', 'Pickup & Drop-off'),
        ('pickup', 'Pickup Only'),
        ('drop', 'Drop-off Only'),
    ], string='Usable For', default='both', required=True)
    website_published = fields.Boolean(
        string='Visible on Website', default=True,
        help='Offer this location to customers on the booking page.')

    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self.env.company.country_id)
    phone = fields.Char()
    mobile = fields.Char()
    email = fields.Char()
    map_url = fields.Char(
        string='Map Link', compute='_compute_map_url', store=False)
    notes = fields.Text(string='Instructions')

    full_address = fields.Char(compute='_compute_full_address')

    @api.depends('street', 'street2', 'city', 'state_id', 'zip', 'country_id')
    def _compute_full_address(self):
        for rec in self:
            parts = [rec.street, rec.street2, rec.city,
                     rec.state_id.name, rec.zip, rec.country_id.name]
            rec.full_address = ', '.join(p for p in parts if p)

    def _compute_map_url(self):
        for rec in self:
            query = rec.full_address or rec.name or ''
            rec.map_url = 'https://maps.google.com/?q=%s' % query.replace(
                ' ', '+') if query else False

    @api.depends('name', 'city')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s (%s)' % (rec.name, rec.city) \
                if rec.city else rec.name

    @api.model
    def _available(self, usage, company=None):
        """Locations offered to customers for 'pickup' or 'drop'."""
        domain = [('website_published', '=', True),
                  ('location_type', 'in', ('both', usage))]
        if company:
            domain.append(('company_id', '=', company.id))
        return self.sudo().search(domain)
