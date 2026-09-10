# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BookingHoliday(models.Model):
    _name = 'odex.booking.holiday'
    _description = 'Workshop Holiday / Closure'
    _order = 'date_from desc'

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one(
        'res.company', string='Branch',
        help='Leave empty to apply to all companies.')
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    closure_type = fields.Selection([
        ('holiday', 'Holiday'),
        ('emergency', 'Emergency Closure'),
    ], default='holiday', required=True)
    active = fields.Boolean(default=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError('"From" date must be before "To" date.')

    @api.model
    def _is_closed(self, date, company=None, branch=None):
        domain = [('date_from', '<=', date), ('date_to', '>=', date)]
        if company:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', company.id)]
        return bool(self.search_count(domain))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._block_existing_slots()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'date_from', 'date_to', 'company_id', 'active'} & set(vals):
            self._block_existing_slots()
        return res

    def _block_existing_slots(self):
        Slot = self.env['odex.booking.slot'].sudo()
        for rec in self.filtered('active'):
            domain = [('date', '>=', rec.date_from), ('date', '<=', rec.date_to)]
            if rec.company_id:
                domain.append(('company_id', '=', rec.company_id.id))
            Slot.search(domain).write({'is_blocked': True})
