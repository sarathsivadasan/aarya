# -*- coding: utf-8 -*-
import ast
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def default_get(self, field_list):
        result = super(SaleOrder, self).default_get(field_list)
        project = self.env["project.project"].search([])
        if project:
            result["project_id"] = project[0].id
        return result

    # title = fields.Selection([('mr', 'Mr.'), ('mrs', 'Mrs.'), ('miss', 'Miss')])
    # is_insurance = fields.Boolean(string="Is Insurance Claim")
    # insurance_company_id = fields.Many2one('res.partner', string='Insurance Company', auto_join=True, tracking=True,
    #                                        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    # project_id = fields.Many2one('project.project', required=True)
    # policy_no = fields.Char("Policy No.")
    # lpo_no = fields.Char("LPO No")
    # lpo_date = fields.Date("LPO Date")
    # claim_no = fields.Char("Claim No.")
    # job_id = fields.Many2one("project.task", string="Job Card")
    vehicle_id = fields.Many2one("fleet.vehicle", string="License Plate")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="vehicle_id.vehicle_make_id",
                                      string="Vehicle Make")
    vehicle_model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    # vehicle_type = fields.Many2one("vehicle.type.custom", string="Vehicle Type",
    #                                related="vehicle.cc_vehicle_type")
    vehicle_color_id = fields.Many2one("vehicle.color", related="vehicle_id.color_id", string="Color")
    vin = fields.Char(string="Chassis No.", related="vehicle_id.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle_id.engin_no")
    # gears = fields.Selection([('automatic', 'Automatic'),
    #                           ('manual', 'Manual')], string='Gears', related="vehicle.cc_gears")
    year = fields.Selection(string="Year", related="vehicle_id.model_year")
    # fuel_type = fields.Selection([
    #     ('petrol', 'Petrol'),
    #     ('diesel', 'Diesel'),
    #     ('gas', 'Gasoline'),
    #     ('electric', 'Electrical')
    # ], string="Fuel Type", related="vehicle.cc_fuel_type")
    odometer = fields.Char(string="Odometer Reading")
    num_word = fields.Char(string="Amount In Words:", compute='_compute_amount_in_word')
    is_job_card_created = fields.Boolean(string="Is Job Created?")
    job_id = fields.Many2one('project.task')

    # remarks = fields.Html('Remark')

    @api.onchange('vehicle_id')
    def onchnage_vehicle(self):
        for rec in self:
            if rec.vehicle_id:
                rec.partner_id = rec.vehicle_id.partner_id

    def _compute_amount_in_word(self):
        for rec in self:
            rec.num_word = str(rec.currency_id.amount_to_text(rec.amount_total)) + ' only'

    # def create_material_requisition(self, job_card_id):
    #     """
    #     Create material requisition
    #     """
    #     material_requisition_obj = self.env['material.purchase.requisition']
    #     employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
    #     material_requisition_id = material_requisition_obj.create({
    #         'employee_id': employee_id.id,
    #         'department_id': employee_id.department_id.id,
    #         'request_date': fields.Date.today(),
    #         'task_id': job_card_id.id
    #     })
    #     return material_requisition_id
    def action_confirm(self):
        res = super().action_confirm()

        job_cost_sheet = self.env['job.cost.sheet']

        for order in self:
            if not order.job_id:
                continue

            # # Avoid duplicate cost sheet lines if needed
            # existing_products = order.job_id.job_cost_sheet_ids.mapped('product_id')

            for line in order.order_line:
                # if line.product_id in existing_products:
                #     continue

                job_cost_sheet.create({
                    'cost_type': line.cost_type,
                    'part_no': line.part_no,
                    'product_id': line.product_id.id,
                    'account_id': line.product_id.categ_id.property_account_income_categ_id.id,
                    'account_analytic_id': False,
                    'quantity': line.product_uom_qty,
                    'uom_id': line.product_uom.id,
                    'custom_price': line.custom_price,
                    'price_factor': line.price_factor,
                    'price_unit': line.price_unit,
                    'invoice_line_tax_ids': line.tax_id,
                    'price_subtotal': line.price_subtotal,
                    'task_id': order.job_id.id,
                    'name': line.name,
                    'discount': line.discount,
                    'vendor_id': line.vendor_id.id,
                    # 'cc_check_box': True,
                    'invoice_line_tax_ids': [(6, 0, line.tax_id.ids)]
                })

        return res

    def action_cancel(self):
        res = super().action_cancel()

        for order in self:
            if not order.job_id:
                continue
            cost_sheet_lines = order.job_id.job_cost_sheet_ids.filtered(
                lambda l: l.product_id in order.order_line.mapped('product_id')
            )
            cost_sheet_lines.unlink()
        return res

    def create_job_card(self):
        """
        Create Job card
        """
        if self.state not in ['sale']:
            raise ValidationError(_('Confirm the order first.'))

        job_card_obj = self.env['project.task']
        job_cost_sheet = self.env['job.cost.sheet']
        # material_requisition_line = self.env['material.purchase.requisition.line']

        job_card = job_card_obj.create({
            'partner_id': self.partner_id.id,
            # 'title': self.title,
            # 'is_insurance': self.is_insurance,
            # 'insurance_company': self.insurance_company_id.id,
            # 'project_id': self.project_id.id,
            # 'policy_no': self.policy_no,
            # 'lpo_no': self.lpo_no,
            # 'lpo_date': self.lpo_date,
            # 'claim_no': self.claim_no,
            'sale_order_id': self.id,
            'company_id': self.company_id.id,
            'is_jobcard': True,
            'vehicle_id': self.vehicle_id.id,
            # 'km_in': self.inspection_id.km_in if self.inspection_id else False,
            # 'km_out': self.inspection_id.km_out if self.inspection_id else False,
            # 'service_due_km': self.service_due_km,
            # 'next_service_date': self.next_service_date,
        })
        # job_card.sale_order_id = self.id
        # job_card.partner_id = self.partner_id.id
        # job_card.company_id = self.company_id.id
        if job_card:
            self.is_job_card_created = True
            job_card.write({'sale_order_id': self.id})
        if self.order_line:
            # cost_sheet_lines = self.order_line.filtered(lambda x: x.cost_type not in ['material', 'spare_parts'])
            # requisition_lines = self.order_line.filtered(lambda x: x.cost_type in ['material', 'spare_parts'])
            cost_sheet_lines = self.order_line
            if cost_sheet_lines:
                for line in cost_sheet_lines:
                    if line.portal_confirmed:
                        job_cost_sheet.create({
                            'cost_type': line.cost_type,
                            'part_no': line.part_no,
                            'product_id': line.product_id.id,
                            'account_id': line.product_id.categ_id.property_account_income_categ_id.id,
                            'account_analytic_id': None,
                            'quantity': line.product_uom_qty,
                            'uom_id': line.product_uom.id,
                            # 'cc_sale_price': line.price_unit,
                            # 'price_custom': line.price_unit,
                            'custom_price': line.custom_price,
                            'price_factor': line.price_factor,
                            'price_unit': line.price_unit,
                            'invoice_line_tax_ids': line.tax_id,
                            'price_subtotal': line.price_subtotal,
                            'task_id': job_card.id,
                            'name': line.name,
                            'discount': line.discount,
                            'vendor_id': line.vendor_id.id,
                            # 'cc_check_box': True,
                            'invoice_line_tax_ids': [(6, 0, line.tax_id.ids)]
                        })

            # if requisition_lines:
            #     material_requisition_id = self.create_material_requisition(job_card)

            #     for line in requisition_lines:
            #         material_requisition_line.create({
            #             'partner_id': False,
            #             'requisition_type': 'internal',
            #             'barcode': line.product_id.barcode,
            #             'product_id': line.product_id.id,
            #             'description': line.product_id.name,
            #             'cc_sale_price': line.price_unit  ,
            #             'qty': line.product_uom_qty,
            #             'uom': line.product_uom.id,
            #             'requisition_id': material_requisition_id.id,
            #             'tax_id': [(6, 0, line.tax_id.ids)]
            #         })
            #     if material_requisition_id:
            #         job_card.cc_stage_id = 4
        return job_card

    def action_view_task(self):
        result = super(SaleOrder, self).action_view_task
        if self.is_job_card_created:
            action = self.env['ir.actions.actions']._for_xml_id('job_card.action_view_job_card')
            action['domain'] = AND([ast.literal_eval(action['domain']), [('sale_order_id', '=', self.id)]])
            return action

    def separate_order_lines(self):
        """
        Separate cost sheet lines
        """
        line = []

        for rec in self:
            if rec.order_line:
                # other_lines = self.order_line.filtered(lambda x: x.cost_type not in ['material', 'spare_parts', 'labour'])
                other_lines = self.order_line.filtered(lambda x: x.cost_type not in ['spare_parts'])
                # labour_lines = self.order_line.filtered(lambda x: x.cost_type in ['labour'])
                # material_lines = self.order_line.filtered(lambda x: x.cost_type in ['material', 'spare_parts'])
                material_lines = self.order_line.filtered(lambda x: x.cost_type in ['spare_parts'])
                if material_lines:
                    for type in sorted(set(material_lines.mapped('cost_type')), reverse=True):
                        cost_sheet_list = []
                        cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                        line.append(cost_sheet_list)
                # if labour_lines:
                #     for type in sorted(set(labour_lines.mapped('cost_type')), reverse=True):
                #         cost_sheet_list = []
                #         cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                #         line.append(cost_sheet_list)
                if other_lines:
                    for type in sorted(set(other_lines.mapped('cost_type')), reverse=True):
                        cost_sheet_list = []
                        cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                        line.append(cost_sheet_list)
        print("line,,,,,,,,,,", line)
        return line


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
    part_no = fields.Char(string="Part No.")

    # 1. Custom Price: Defaults to product unit price and remains manually editable
    custom_price = fields.Float(
        string='Custom Price',
        compute='_compute_custom_price',
        store=True,
        readonly=False,
        help='Base price before markup. Defaults to standard unit price but can be manually edited.',
    )

    # 2. Markup percentage fetched from customer contact
    price_factor = fields.Float(
        string='Markup (%)',
        compute='_compute_markup_prices',
        store=True,
        readonly=False,
        help='Markup percentage retrieved from customer contact',
    )

    # 3. Readonly computed field for price after markup (applies to hidden price_unit)
    # price_after_markup = fields.Float(
    #     string='Sale Price',
    #     compute='_compute_markup_prices',
    #     store=True,
    #     readonly=True,
    #     help='Final sale price after applying percentage markup.',
    # )

    # cc_sale_price = fields.Float(string="Cost Price", related="product_id.standard_price")

    @api.onchange('product_id')
    def _onchange_product_id(self):
        result = super(SaleOrderLine, self)._onchange_product_id()
        if self.product_id:
            self.cost_type = self.product_id.cost_type
            self.parts_type = self.product_id.parts_type
            self.part_no = self.product_id.barcode
        else:
            self.cost_type = 'spare_parts'
            self.parts_type = 'original'
            self.part_no = ''
        return result

    @api.onchange('part_no')
    def _onchange_part_no(self):
        if self.part_no:
            product_id = self.env['product.product'].search([('barcode', '=', self.part_no)], limit=1)
            if product_id:
                self.product_id = product_id.id

    @api.depends('product_id', 'product_uom', 'company_id')
    def _compute_custom_price(self):
        """Sets custom_price default to whatever standard unit price the product takes."""
        for line in self:
            if line.product_id:
                # Fetch standard computed list price / pricelist value
                line.custom_price = line.product_id.lst_price

    @api.depends('custom_price', 'cost_type', 'order_id.partner_id')
    def _compute_markup_prices(self):
        for line in self:
            partner = line.order_id.partner_id
            raw_markup = 0.0

            if partner:
                if line.cost_type == 'spare_parts':
                    raw_markup = partner.markup_spare_parts
                elif line.cost_type == 'labour':
                    raw_markup = partner.markup_labor
                elif line.cost_type == 'sublet':
                    raw_markup = partner.markup_sublet

            # --- PERCENTAGE CONVERSION LOGIC ---
            # If the value entered on res.partner is a whole number (e.g. 10 for 10%),
            # convert it to decimal ratio (0.10) for widget="percentage" and math.
            if raw_markup > 1.0:
                markup_ratio = raw_markup / 100.0
            else:
                markup_ratio = raw_markup

            # Assign ratio to price_factor (0.10 renders as 10% in UI)
            line.price_factor = markup_ratio

            # Calculate Sale Price: Custom Price + (Custom Price * 10%)
            base = line.custom_price or 0.0
            final_price = base * (1.0 + markup_ratio)

            # line.price_after_markup = final_price
            line.price_unit = final_price

    # def action_increase_price(self):
    #     """
    #     Increase price by 10 %
    #     """
    #     for rec in self:
    #         if rec.price_unit:
    #             rec.price_unit = rec.price_unit * 1.1

# class ProjectTask(models.Model):
#     _inherit = 'project.task'

#     sale_order_id = fields.Many2one("sale.order", string="Sale Order")
#     account_move_id = fields.Many2one("account.move", string="Bills")
