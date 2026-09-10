# -*- coding: utf-8 -*-

from odoo import api, fields, models

class CustomerDeclaration(models.Model):
    _name = "customer.declaration"

    name = fields.Text(string="Customer Declaration")
    include = fields.Boolean(string="Include In Job Card")