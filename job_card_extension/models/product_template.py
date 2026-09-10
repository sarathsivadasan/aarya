# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # product_location_id = fields.Many2one("stock.location", string="Location",
    #                                       default=8, compute="compute_location")

    cost_type = fields.Selection(
        [('spare_parts', 'Spare Parts'),
         ('discount', 'Discount'),
         ('service', 'Service'),
         ('consumables', 'Consumables'),
         ('labour', 'Labour'),
         ('sublet', 'Sublet'),
         ('tyre', 'Tyre'),
         ('scrap', 'Scrap'),
         ('paint', 'Paint'),
         ],
        string='Type',
        default='spare_parts',
    )
    parts_type = fields.Selection(
        [('original', 'Original'),
         ('duplicate', 'Thijari(Duplicate)'),
         ('used', 'Used'),
         ],
        string='Parts Type',
        default='original',
    )
    assign_hours = fields.Float(string="Assign Hours")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", string="Brand")

    # @api.onchange('qty_available')
    # @api.depends('qty_available')
    # def compute_location(self):
    #     for rec in self:
    #         rec.product_location_id = False
    #         if rec.qty_available:
    #             quant_id = rec.env['stock.quant'].search([('product_tmpl_id', '=', rec.id)], limit=1)
    #             if quant_id and quant_id.location_id:
    #                 rec.product_location_id = quant_id.location_id.id

    # def compute_location(self):
    #     for rec in self:
    #         rec.product_location_id = False
    #         if rec.qty_available:
    #             quant_id = rec.product_variant_id.stock_quant_ids.filtered(lambda x:x.quantity > 0 and x.inventory_date)
    #             if quant_id:
    #                 rec.product_location_id = quant_id[0].location_id.id
