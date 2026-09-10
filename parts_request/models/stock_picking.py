# -*- coding: utf-8 -*-

from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    jobcard_part_requisition_id = fields.Many2one(
        'jobcard.part.requisition',
        string='Jobcard Part Requisition',
        readonly=True,
        copy=True
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    jobcard_part_requisition_id = fields.Many2one(
        'jobcard.part.requisition',
        string='Jobcard Part Requisition',
        readonly=True,
        copy=True
    )
