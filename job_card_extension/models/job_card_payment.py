# -*- coding: utf-8 -*-
from odoo import api, fields, models

class JobCardPayment(models.Model):
    _name = "job.card.payment"

    name = fields.Char("Category")
    hours = fields.Float("Hours", digit=(16,2))
    payment = fields.Monetary(string='Payment', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.user.company_id.currency_id.id)
