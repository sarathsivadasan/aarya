# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    odex_booking_terms_url = fields.Char(
        string='Terms & Conditions URL',
        config_parameter='odex_workshop_booking.terms_url')
    odex_booking_help_phone = fields.Char(
        string='Help Phone Number',
        config_parameter='odex_workshop_booking.help_phone')
    odex_booking_auto_confirm = fields.Boolean(
        string='Auto-Confirm Website Bookings',
        config_parameter='odex_workshop_booking.auto_confirm',
        help='If enabled, website bookings are confirmed immediately instead of Requested.')
