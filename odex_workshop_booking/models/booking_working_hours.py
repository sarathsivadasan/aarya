# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BookingWorkingHours(models.Model):
    _name = 'odex.booking.working.hours'
    _description = 'Branch Working Hours'
    _order = 'dayofweek, hour_from'

    company_id = fields.Many2one(
        'res.company', string='Workshop', required=True, ondelete='cascade',
        default=lambda self: self.env.company)
    dayofweek = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
    ], string='Day of Week', required=True, default='0')
    hour_from = fields.Float(string='From', required=True)
    hour_to = fields.Float(string='To', required=True)

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for rec in self:
            if not (0.0 <= rec.hour_from < 24.0 and 0.0 < rec.hour_to <= 24.0):
                raise ValidationError('Hours must be between 00:00 and 24:00.')
            if rec.hour_from >= rec.hour_to:
                raise ValidationError('"From" must be earlier than "To".')
