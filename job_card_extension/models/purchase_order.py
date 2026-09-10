# -*- coding: utf-8 -*-

from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    job_id = fields.Many2one('project.task', string="Job Card")

    # Vehicle Details
    vehicle_id = fields.Many2one("fleet.vehicle", string="License Plate")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="vehicle_id.vehicle_make_id",
                                      string="Vehicle Make")
    vehicle_model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    vehicle_color_id = fields.Many2one("vehicle.color", related="vehicle_id.color_id", string="Color")
    vin = fields.Char(string="Chassis No.", related="vehicle_id.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle_id.engin_no")
    year = fields.Selection(string="Year", related="vehicle_id.model_year")


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    part_no = fields.Char(string="Part No.")
    parts_type = fields.Selection(
        [('original', 'Original'),
         ('duplicate', 'Thijari(Duplicate)'),
         ('used', 'Used'),
         ],
        string='Parts Type',
        default='original',
    )
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", string="Brand")

    @api.onchange('part_no')
    def _onchange_part_no(self):
        if self.part_no:
            product_id = self.env['product.product'].search([('barcode', '=', self.part_no)], limit=1)
            if product_id:
                self.product_id = product_id.id

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = super(PurchaseOrderLine, self).onchange_product_id()
        if self.product_id:
            self.part_no = self.product_id.barcode
            self.parts_type = self.product_id.parts_type
            self.vehicle_make_id = self.product_id.vehicle_make_id.id
        else:
            self.part_no = ''
            self.parts_type = ''
            self.vehicle_make_id = ''
        return result


