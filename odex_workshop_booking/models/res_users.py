# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    booking_company_id = fields.Many2one(
        'res.company', string='Default Workshop',
        help='Pre-selected on new bookings and working schedules for this user.')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['booking_company_id']
