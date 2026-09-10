# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # fleet_service_id = fields.Many2one('fleet.vehicle.log.services', string="Fleet Service")
    inspection_id = fields.Many2one('project.task', string="Inspection No.")

    # @api.onchange('fleet_service_id')
    # def onchange_fleet_service_id(self):
    #     for rec in self:
    #         if rec.fleet_service_id:
    #             """
    #                 Create Estimate Lines
    #             """
    #             sale_order_line_obj = self.env['sale.order.line']
    #             if rec.fleet_service_id.fleet_service_sheet_ids:
    #                 rec.order_line = [(5, 0, 0)]  # Clear existing sale lines
    #                 service_sheet_ids = rec.fleet_service_id.fleet_service_sheet_ids
    #                 for line in service_sheet_ids:
    #                     lines = []
    #                     vals = {
    #                         'order_id': rec.id or rec._origin.id,
    #                         'cost_type': line.cost_type,
    #                         'product_id': line.product_id.id,
    #                         # 'account_id': line.account_id.id,
    #                         # 'account_analytic_id': None,
    #                         'product_uom_qty': line.quantity,
    #                         'product_uom': line.uom_id.id,
    #                         # 'cc_sale_price': line.cc_sale_price,
    #                         'price_unit': line.price_unit,
    #                         # 'price_custom': line.price_custom,
    #                         # 'price_factor': line.price_factor.id,
    #                         # 'barcode_custom': line.barcode_custom,
    #                         'tax_id': line.invoice_line_tax_ids,
    #                         'price_subtotal': line.price_subtotal,  
    #                         'name': line.name,
    #                         'discount': line.discount,
    #                         }
    #                     lines.append((0, 0, vals))
    #                     rec.order_line = lines

    def create_job_card(self):
        result = super(SaleOrder, self).create_job_card()
        if self.inspection_id:
            job_requested_services = self.env['job.requested.service']
            parts_ids = self.env['vehicle.inspection.part']
            result.image1_name = self.inspection_id.image1_name
            result.image2_name = self.inspection_id.image2_name
            result.image3_name = self.inspection_id.image3_name
            result.image4_name = self.inspection_id.image4_name
            result.image5_name = self.inspection_id.image5_name
            result.image6_name = self.inspection_id.image6_name
            result.image7_name = self.inspection_id.image7_name
            result.image8_name = self.inspection_id.image8_name
            result.image9_name = self.inspection_id.image9_name
            result.image10_name = self.inspection_id.image10_name
            result.image11_name = self.inspection_id.image11_name
            result.image12_name = self.inspection_id.image12_name

            result.image1 = self.inspection_id.image1
            result.image2 = self.inspection_id.image2
            result.image3 = self.inspection_id.image3
            result.image4 = self.inspection_id.image4
            result.image5 = self.inspection_id.image5
            result.image6 = self.inspection_id.image6
            result.image7 = self.inspection_id.image7
            result.image8 = self.inspection_id.image8
            result.image9 = self.inspection_id.image9
            result.image10 = self.inspection_id.image10
            result.image11 = self.inspection_id.image11
            result.image12 = self.inspection_id.image12

            result.image1_desc = self.inspection_id.image1_desc
            result.image2_desc = self.inspection_id.image2_desc
            result.image3_desc = self.inspection_id.image3_desc
            result.image4_desc = self.inspection_id.image4_desc
            result.image5_desc = self.inspection_id.image5_desc
            result.image6_desc = self.inspection_id.image6_desc
            result.image7_desc = self.inspection_id.image7_desc
            result.image8_desc = self.inspection_id.image8_desc
            result.image9_desc = self.inspection_id.image9_desc
            result.image10_desc = self.inspection_id.image10_desc
            result.image11_desc = self.inspection_id.image11_desc
            result.image12_desc = self.inspection_id.image12_desc
            # job_work_description = self.env['job.work.description']
            if self.inspection_id.requested_services_ids:
                for service in self.inspection_id.requested_services_ids:
                    job_requested_services.create({
                        'product_id': service.product_id.id,
                        'assign_hours': service.assign_hours,
                        'remark': service.remark,
                        'task_id': result.id,
                        'is_added_in_timesheet': service.is_added_in_timesheet,        
                    })
            if self.inspection_id.inspection_part_ids:
                for parts in self.inspection_id.inspection_part_ids:
                    parts_ids.create({
                        'product_id': parts.product_id.id,
                        'part_no': parts.part_no,
                        'part': parts.part,
                        'parts_type': parts.parts_type,
                        'inspection_id': result.id,
                        'quantity': parts.quantity, 
                        'is_confirm': False,
                        'from_inspection': True,       
                    })
            if self.inspection_id.quality_checklist_ids:
                for qc in self.inspection_id.quality_checklist_ids:
                    for qc1 in result.quality_checklist_ids:
                        if qc.name == qc1.name:
                            qc1.description = qc.description
                            qc1.check_mark = qc.check_mark
            # if self.inspection_id.work_description_ids:
            #     for work in self.inspection_id.work_description_ids:
            #         job_work_description.create({
            #         'name': work.name,
            #         'remark': work.remark,
            #         'task_id': result.id,
            #         })
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    vendor_id = fields.Many2one('res.partner', string="Vendor")

    @api.depends('product_id', 'product_uom', 'company_id')
    def _compute_custom_price(self):
        """Sets custom_price default to whatever standard unit price the product takes."""
        for line in self:
            if line.product_id and not self._context.get('from_inspection'):
                # Fetch standard computed list price / pricelist value
                line.custom_price = line.product_id.lst_price