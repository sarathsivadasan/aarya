# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseMultiRFQ(models.Model):
    _inherit = 'purchase.multi.rfq'

    inspection_id = fields.Many2one('project.task', string="Inspection No.")