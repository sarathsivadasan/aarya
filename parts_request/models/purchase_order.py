# -*- coding: utf-8 -*-

from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for line in self.order_line:
            if line.part_requisition_id:
                line.part_requisition_id.po_id = self.id
        return res
    
   
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    part_requisition_id = fields.Many2one(
        'jobcard.part.requisition',
        string='Part Requisition',
        copy=False
    )

