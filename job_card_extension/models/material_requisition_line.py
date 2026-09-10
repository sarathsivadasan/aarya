# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order.line'

    is_material_purchase_requisition_line = fields.Boolean(string="Is Material Purchase Requisition?")


class MaterialPurchaseRequisition(models.Model):
    _inherit = 'material.purchase.requisition'

    is_approved = fields.Boolean(string="Is Approved?")

    def user_approve(self):
        for rec in self:
            rec.userrapp_date = fields.Date.today()
            rec.approve_employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.is_approved = True
            rec.state = 'approve'
            if rec.task_id:
                rec.task_id.cc_stage_id=2
            # create picking and remove products from inventory
            rec.request_stock()

    @api.model
    def _prepare_pick_vals(self, line=False, stock_id=False):
        pick_vals = super(MaterialPurchaseRequisition, self)._prepare_pick_vals(line, stock_id)
        pick_vals.update({
            'product_uom_qty': line.qty
        })
        return pick_vals

    def redirect_vin(self):
        for each in self:
            if each.task_id and each.task_id.vin:
                return {
                        'type': 'ir.actions.act_url',
                        'url': "https://www.allparts.ae/search.html?article="+each.task_id.vin+"&withAnalogs=1",
                        'target': 'blank',
                    }
            else:
                raise UserError(_("VIN Number Not Exist"))


class MaterialPurchaseRequisitionLine(models.Model):
    _inherit = 'material.purchase.requisition.line'

    added_in_cost_sheet = fields.Boolean(string="Added in cost sheet")
    is_approved = fields.Boolean(related="requisition_id.is_approved", string="Is Approved")
    barcode = fields.Char("Part No.", compute="compute_barcode", store=True, readonly=False)
    stock = fields.Float(related="product_id.qty_available", readonly=False)
    location_id = fields.Many2one(related="product_id.product_location_id")
    cost_price = fields.Float(related="product_id.standard_price")
    sale_price = fields.Float(related="product_id.list_price")
    cc_sale_price = fields.Float()
    total_price = fields.Float(string="Subtotal", compute="compute_total_price")
    tax_id = fields.Many2many('account.tax', string='Taxes')

    @api.onchange('cost_price', 'sale_price', 'qty')
    @api.depends('cost_price', 'sale_price', 'qty')
    def compute_total_price(self):
        """
        Compute total price
        """
        for rec in self:
            rec.total_price = 0.00
            if rec.requisition_type:
                if rec.requisition_type == "internal" and rec.sale_price:
                    rec.total_price = rec.qty * rec.sale_price
                if rec.requisition_type == "purchase" and rec.cost_price:
                    rec.total_price = rec.qty * rec.cost_price


    @api.onchange('barcode', 'product_id')
    @api.depends('barcode', 'product_id')
    def compute_barcode(self):
        for rec in self:
            if rec.barcode:
                product_id = rec.product_id.search([
                    ('barcode', '=', rec.barcode)
                ], limit=1)
                if product_id:
                    rec.product_id = product_id.id
            elif rec.product_id:
                rec.barcode = rec.product_id.barcode

    @api.onchange("product_id")
    def onchange_product(self):
        """
        On change product set location
        """
        for rec in self:
            if rec.product_id:
                rec.location_id = 8
                rec.barcode = rec.product_id.barcode
                
    def action_requisition_approve(self):
        """
        Approve Material Requisition Lines
        """
        self.is_approved = True
        return True

    def action_add_line_in_cost_sheet(self):
        """
        Add requisition lines in cost sheet
        """
        job_cost_sheet = self.env['job.cost.sheet']
        account = self.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=None)['income']
        job_cost_sheet.create({
            'cost_type': 'spare_parts',
            'product_id': self.product_id.id,
            'name': self.description,
            'quantity': self.qty,
            'uom_id': self.uom.id,
            'account_id': account.id,
            'cc_sale_price': self.cc_sale_price,
            'price_custom': self.cc_sale_price,
            'price_unit': self.cc_sale_price,
            'price_subtotal': self.qty * self.cc_sale_price,
            'task_id': self.task_id.id,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)]

        })
        self.added_in_cost_sheet = True
