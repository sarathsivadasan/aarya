# -*- coding: utf-8 -*-
from odoo import fields, models


class BookingServiceType(models.Model):
    _name = 'odex.booking.service.type'
    _description = 'Booking Service Type'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean(string='Visible on Website', default=True)
    icon = fields.Char(help='Font Awesome icon class, e.g. fa-wrench')
    description = fields.Text(translate=True)
    estimated_duration = fields.Float(string='Estimated Duration (Hours)', default=1.0)
    color = fields.Integer(string='Color Index')
