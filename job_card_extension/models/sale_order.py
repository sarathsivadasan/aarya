# -*- coding: utf-8 -*-

from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    job_id = fields.Many2one("project.task", string="Job")
    next_service_date = fields.Date('Next Service Date')
    service_due_km = fields.Char('Service Due KM')

    def create_job_card(self):
        """
        Create Job card
        """
        job_card_obj = self.env['project.task']
        job_cost_sheet = self.env['job.cost.sheet']

        job_card = job_card_obj.create({
            'partner_id': self.partner_id.id,
            'service_due_km': self.service_due_km,
            'next_service_date': self.next_service_date,
            'is_jobcard': True
        })
        if self.order_line:
            for line in self.order_line:
                job_cost_sheet.create({
                    'product_id': line.product_id.id,
                    'account_id': line.product_id.categ_id.property_account_expense_categ_id.id,
                    'account_analytic_id': None,
                    'quantity': line.product_uom_qty,
                    'uom_id': line.product_uom.id,
                    'cc_sale_price': line.price_unit,
                    'computed_cost_price': line.price_unit,
                    'price_unit': line.price_unit,
                    'invoice_line_tax_ids': line.tax_id,
                    'price_subtotal': line.price_subtotal,
                    'task_id': job_card.id,
                    'name': line.product_id.name,
                    'cc_check_box': True
                })
        return True