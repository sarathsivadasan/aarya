# -*- coding: utf-8 -*-
import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    num_word = fields.Char(string="Amount In Words:", compute='_compute_amount_in_word')
    # title = fields.Selection([('mr', 'Mr.'), ('mrs', 'Mrs.'), ('miss', 'Miss')])
    # project_id = fields.Many2one('project.project')
    # is_job_card_created = fields.Boolean(string="Is Job Created?")
    # repair_category = fields.Many2one(related="cc_job_card.repair_category")
    # repair_sub_category = fields.Many2many(related="cc_job_card.repair_sub_category_ids")
    # invoice_journal_name = fields.Char(string="Payment Source", compute="compute_invoice_number")
    # invoice_date = fields.Date(string='Invoice/Bill Date', readonly=True, index=True, copy=False,
    #     states={'draft': [('readonly', False)]}, default=fields.Date.today())

    # next_service_date = fields.Date('Next Service Date')
    # service_due_km = fields.Char('Service Due KM')

    @api.onchange('payment_reference', 'name')
    @api.depends('payment_reference', 'name')
    def compute_invoice_number(self):
        """
        Get last invoice number
        """
        for rec in self:
            rec.invoice_journal_name = ""
            if rec.payment_reference:
                invoice_payment_id = rec.env['account.payment'].search([('ref', '=', rec.payment_reference)],
                                                                       order="create_date desc", limit=1)
                rec.invoice_journal_name = invoice_payment_id.journal_id.name if invoice_payment_id and invoice_payment_id.journal_id else False


    @api.onchange('partner_id')
    def onchange_partner(self):
        for rec in self:
            if rec.cc_job_card:
                rec.partner_excess_amount = rec.cc_job_card.partner_id.id
            else:
                if rec.partner_id:
                    rec.partner_excess_amount = rec.partner_id.id

    def create_job_cost_sheet_line(self):
        """
        Create Job card
        """
        if self.state not in ['posted']:
            raise ValidationError(_('Confirm the Bill first.'))
        job_cost_sheet = self.env['job.cost.sheet']
        sheet_lines = []
        print("2398rygkjamssfsdfd")
        if self.invoice_line_ids:
            for rec in self.invoice_line_ids:
                vals = {
                    'cost_type': rec.cc_cost_type,
                    'product_id': rec.product_id.id,
                    'account_id': rec.account_id.id,
                    'account_analytic_id': rec.analytic_account_id.id if rec.analytic_account_id else None,
                    'quantity': rec.quantity,
                    'uom_id': rec.product_uom_id.id,
                    'cc_sale_price': rec.cc_sale_price,
                    # 'price_unit': rec.cc_sale_price if rec.cc_sale_price else rec.price_unit,
                    'price_unit': rec.price_unit,
                    'discount': rec.discount,
                    'invoice_line_tax_ids': rec.tax_ids,
                    'price_subtotal': rec.price_subtotal,
                    'task_id': rec.move_id.cc_job_card.id,
                    'cc_account_move_line_id': rec.id,
                    'name': rec.name or rec.product_id.name,
                    'cc_check_box': True

                }
                sheet_lines.append(vals)
            print("sheet_linessheet_lines",sheet_lines)
            job_cost_sheet.create(sheet_lines)
            self.is_job_card_created = True

    def _compute_amount_in_word(self):
        for rec in self:
            rec.num_word = str(rec.currency_id.amount_to_text(round(rec.amount_total))) + ' only'

    def get_amount_related_information(self):
        total_without_discount = []
        for i in self.invoice_line_ids:
            total_without_discount.append(i.price_unit * i.quantity)
        discount = round(sum(total_without_discount) - self.amount_untaxed, 2)
        data_dict = {
            'currency_name': self.currency_id.name,
            'total_without_discount': sum(total_without_discount) or 0.0,
            'discount': discount or 0.0,
            'gross': self.amount_untaxed or 0.0,
            'tax_amount': self.amount_tax or 0.0,
            'net_amount': self.amount_total or 0.0,
            'advance_amount': 0.0,
            'amount_paid': round((self.amount_total - self.amount_residual), 2) or 0.0,
            'balance_amount': self.amount_residual or 0.0,
            'excess_amount': self.excess_amount or 0.0,
        }
        return data_dict

    def create_gatepass(self):
        for rec in self:
            job_card = rec.cc_job_card
            if job_card:
                job_card.cc_stage_value = 'out'
                job_card.date_end = datetime.datetime.now()

    def print_gatepass(self):
        if not self.cc_job_card:
            raise ValidationError("Job Card Is Not Selected!!!!!!")
        rtn = self.env.ref('job_card_extension.custom_print_gate_pass_template').report_action(self.cc_job_card.id)
        self.message_post(body=self.env.user.name + "-> Has Printed The Gate Pass")
        return rtn


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_instock_location_domain(self):
        return [('quant_ids', 'in', self.in_stock_quants.ids)]

    barcode_custom = fields.Char("Part No.", compute="compute_barcode_custom", store=True, readonly=False)
    in_stock_quants = fields.Many2many("stock.quant", 'move_line_quant_relation', 'move_line_id', 'quant_id', 'Quant',
                                       compute="compute_in_stock_quants")
    in_stock_quant = fields.Many2one('stock.quant', compute="compute_in_stock_quant")
    in_stock_location_id = fields.Many2one('stock.location', 'Location', compute="compute_location_set",
                                           domain="[('usage','=', 'internal')]", readonly=False)
    in_stock_quantity = fields.Integer('Total Qty', compute="compute_in_stock_quantity")
    task_id = fields.Many2one(related="move_id.cc_job_card", string="Job Card")
    profit_loss = fields.Float(string="P&L", compute="_compute_profit_and_loss", default=0.0)
    computed_cost_price = fields.Float(
        string='Cost Price',
        digits='Product Price', store=True, compute="_compute_price"
    )
    total_sale_price = fields.Float(
        string='Sale Price',
        digits='Product Price', store=True, compute="_compute_price"
    )
    computed_price_unit = fields.Float(
        string='Price',
        digits='Product Price', store=True
    )

    cloned_price_unit = fields.Float(
        string='Sale Price',
        digits='Product Price', store=True, compute="_compute_cloned_price_unit", readonly=False
    )

    invoice_date = fields.Date(related="move_id.invoice_date")
    stock = fields.Float(related="product_id.qty_available", readonly=False)

    @api.onchange('price_unit')
    @api.depends('price_unit')
    def _compute_cloned_price_unit(self):
        """
        Compute clone of price unit
        """
        for rec in self:
            if rec.price_unit:
                rec.cloned_price_unit = rec.price_unit

    # @api.onchange('cloned_price_unit', 'price_unit')
    # @api.depends('cloned_price_unit', 'price_unit')
    # def _compute_cloned_price_unit(self):
        """
        Compute clone of price unit
        """ 
            # for each in rec:
                # if rec.cloned_price_unit:
                #     rec.price_unit = rec.cloned_price_unit
                # elif rec.price_unit:
                #     rec.cloned_price_unit = rec.price_unit

    @api.depends("cloned_price_unit", "price_unit")
    def _compute_price(self):
        """
        Compute profit and loss based on cost and sale price
        """
        for rec in self:
            rec.computed_cost_price = rec.product_id.standard_price
            rec.total_sale_price = rec.cloned_price_unit * rec.quantity

    @api.depends("cc_sale_price", "price_unit")
    def _compute_profit_and_loss(self):
        """
        Compute profit and loss based on cost and sale price
        """
        for rec in self:
            rec.profit_loss = 0.0
            if rec.total_sale_price and rec.computed_cost_price:
                rec.profit_loss = rec.total_sale_price - rec.computed_cost_price

    def action_increase_price(self):
        """
        Increase price by 10 %
        """
        for rec in self:
            if rec.price_unit and rec.move_id.state in ['draft']:
                rec.computed_price_unit = rec.price_unit * 1.1

    def write(self, vals):
        if "computed_price_unit" in vals:
            vals['price_unit'] = vals.get('computed_price_unit')
        res = super(AccountMoveLine, self).write(vals)
        return res


    @api.onchange('product_id')
    @api.depends('product_id')
    def compute_in_stock_quants(self):
        for rec in self:
            if rec.product_id:
                # rec.price_unit = rec.product_id.lst_price
                quants = rec.env['stock.quant'].search([
                    ('product_id', '=', rec.product_id.id)
                ])
                rec.in_stock_quants = [(6, 0, quants.ids)]
            else:
                rec.in_stock_quants = False

    @api.onchange('in_stock_location_id', 'product_id')
    @api.depends('in_stock_location_id', 'product_id')
    def compute_in_stock_quant(self):
        for rec in self:
            quant = rec.env['stock.quant'].search([
                ('location_id', '=', rec.in_stock_location_id.id),
                ('quantity', '>', 0)], limit=1)
            if quant:
                rec.in_stock_quant = quant.id
            else:
                rec.in_stock_quant = False

    @api.onchange('product_id')
    @api.depends('product_id')
    def compute_location_set(self):
        for rec in self:
            quant = rec.env['stock.quant'].search([
                ('product_id', '=', rec.product_id.id),
                ('quantity', '>', 0)], limit=1)
            if quant:
                rec.in_stock_location_id = quant.location_id.id
                rec.in_stock_quant = quant.id
            else:
                rec.in_stock_location_id = rec.in_stock_location_id
                rec.in_stock_quant = rec.in_stock_quant

    @api.onchange('barcode_custom', 'product_id')
    @api.depends('barcode_custom', 'product_id')
    def compute_barcode_custom(self):
        for rec in self:
            if rec.barcode_custom:
                product_id = rec.product_id.search([
                    ('barcode', '=', rec.barcode_custom)
                ], limit=1)
                if product_id:
                    rec.product_id = product_id.id
            elif rec.product_id:
                rec.barcode_custom = rec.product_id.barcode

    @api.onchange('product_id')
    def onchange_product_change_barcode_custom(self):
        for rec in self:
            if rec.product_id:
                rec.barcode_custom = rec.product_id.barcode
                rec.cc_cost_type = rec.product_id.cost_type

    @api.onchange('in_stock_location_id')
    @api.depends('in_stock_location_id')
    def compute_in_stock_quantity(self):
        for rec in self:
            if rec.in_stock_quant.product_id and rec.in_stock_quant.product_id.id == rec.product_id.id:
                rec.in_stock_quantity = rec.in_stock_quant.quantity
            else:
                rec.in_stock_quantity = 0

    lpo_no = fields.Char(related='task_id.lpo_no')
    odometer = fields.Char(related='task_id.odometer')
    cc_vehicle_model = fields.Many2one("fleet.vehicle.model", related="task_id.cc_vehicle_model")
    register_no = fields.Char(related='task_id.register_no')
    requested_services = fields.Char('Job Description')
    user_ids = fields.Many2many(string="Service Advisor", related='task_id.user_ids')
    repair_category = fields.Many2one(related="task_id.repair_category", string="Business")
    repair_sub_category = fields.Many2many(related="task_id.repair_sub_category_ids", string="Job Type")
    total_cost = fields.Float(string='Cost Price Sub Total', compute='_compute_all_line_data', store=True, )
    labour = fields.Float(string='Labour', compute='_compute_all_line_data', store=True, )
    consumables = fields.Float(string='Consumables', compute='_compute_all_line_data', store=True, )
    material = fields.Float(string='Material', compute='_compute_all_line_data', store=True, )
    sublet = fields.Float(string='Sublet', compute='_compute_all_line_data', store=True, )
    spare_parts = fields.Float(string='Spare Parts', compute='_compute_all_line_data', store=True, )
    custom_discount = fields.Float(string='Discount', compute='_compute_all_line_data', store=True, )
    service = fields.Float(string='Service', compute='_compute_all_line_data', store=True, )
    parts_markup_amount = fields.Float(string='Parts Markup Amount', compute='_compute_all_line_data', store=True, )
    computed_gross_margin = fields.Float(string="Gross Margin", compute="_compute_all_line_data")
    # total_parts_markup = fields.Float(string='Total Parts With Mark up', compute='_compute_all_line_data', store=True, )
    # amount_untaxed = fields.Monetary(store=True, related='move_id.amount_untaxed')
    # amount_tax = fields.Monetary(store=True, related='move_id.amount_tax')
    # amount_total = fields.Monetary(store=True, related='move_id.amount_total')

    @api.depends("price_unit")
    def _compute_all_line_data(self):
        for rec in self:
            rec.total_cost = rec.computed_cost_price * rec.quantity
            rec.computed_gross_margin = rec.total_sale_price - rec.total_cost
            rec.spare_parts = rec.price_custom * rec.quantity if rec.cc_cost_type == 'spare_parts' else 0.0
            rec.labour = rec.price_custom * rec.quantity if rec.cc_cost_type == 'labour' else 0.0
            rec.material = rec.price_custom * rec.quantity if rec.cc_cost_type == 'material' else 0.0
            rec.consumables = rec.price_custom * rec.quantity if rec.cc_cost_type == 'consumables' else 0.0
            rec.sublet = rec.price_custom * rec.quantity if rec.cc_cost_type == 'sublet' else 0.0
            rec.custom_discount = rec.price_custom * rec.quantity if rec.cc_cost_type == 'discount' else 0.0
            rec.service = rec.price_custom * rec.quantity if rec.cc_cost_type == 'service' else 0.0
            rec.parts_markup_amount = rec.price_unit * rec.quantity - rec.price_custom*rec.quantity

    # @api.depends("price_unit")
    # def _compute_all_line_data(self):
    #     """
    #     Compute profit and loss based on cost and sale price
    #     """
    #     for rec in self:
    #         total_cost = rec.move_id.invoice_line_ids.mapped(
    #             lambda x: x.computed_cost_price * x.quantity)
    #         spare_parts_cost = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'spare_parts').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         spare_parts_price_subtotal = rec.move_id.invoice_line_ids.filtered(
    #             lambda x: x.cc_cost_type == 'spare_parts').mapped(
    #             lambda x: x.price_subtotal)
    #         material = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'material').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         overhead = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'overhead').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         labour = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'labour').mapped(
    #             lambda x: x.price_subtotal)
    #         consumables = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'consumables').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         paint_material = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'paint_material').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         paint_material_cog = rec.move_id.invoice_line_ids.filtered(
    #             lambda x: x.cc_cost_type == 'paint_material_cog').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         mechanical_cog = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'mechanical_cog').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         sublet = rec.move_id.invoice_line_ids.filtered(lambda x: x.cc_cost_type == 'sublet').mapped(
    #             lambda x: x.price_custom * x.quantity)
    #         rec.total_cost = sum(total_cost)
    #         rec.labour = sum(labour)
    #         rec.consumables = sum(consumables)
    #         rec.material = sum(material)
    #         rec.sublet = sum(sublet)
    #         rec.spare_parts = sum(spare_parts_cost)
    #         rec.parts_markup_amount = sum(spare_parts_price_subtotal) - sum(
    #             spare_parts_cost)
    #         rec.total_parts_markup = sum(spare_parts_price_subtotal)
    #         rec.requested_services = rec.move_id.cc_job_card.requested_services_ids.mapped('name')


class MoveLineReportXlsx(models.AbstractModel):
    _name = 'report.job_card_extension.move_line_xlsx_report'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, record):
        wizard_data = record
        if data.get('lines_data'):
            import re
            ids = list(map(int, re.findall(r'\d+', data.get('lines_data'))))
            record = data.get('lines_data')
            record = self.env['account.move.line'].browse(ids)
        H1 = workbook.add_format({'font_size': 28, 'align': 'center', 'bold': True})
        H3 = workbook.add_format({'font_size': 14, 'align': 'center', 'bold': True})
        H4 = workbook.add_format({'font_size': 12, 'align': 'left', 'bold': True, 'text_wrap': True})
        H5 = workbook.add_format({'font_size': 10, 'align': 'left'})
        H5_float = workbook.add_format({'font_size': 10, 'align': 'left', 'num_format': '0.00'})
        H5_percentage = workbook.add_format({'font_size': 10, 'align': 'left', 'num_format': '0.00%'})
        date_format = workbook.add_format({'num_format': 'dd-mmm-yy'})
        date_format2 = workbook.add_format({'font_size': 14, 'num_format': 'dd/mm/yy'})
        sheet_inv = workbook.add_worksheet('Invoice Report')
        # # sheet_credit_note = workbook.add_worksheet('Tax Credit Note Report')
        #
        # #################### Headings  Inv ##############################
        sheet_inv.write(8, 0, "SR No.", H4)
        sheet_inv.write(8, 1, "LPO No", H4)
        sheet_inv.write(8, 2, "Invoice No", H4)
        sheet_inv.write(8, 3, "Invoice Date", H4)
        sheet_inv.write(8, 4, "Customer", H4)
        sheet_inv.write(8, 5, "Job card No", H4)
        sheet_inv.write(8, 6, "Odometer Reader", H4)
        sheet_inv.write(8, 7, "Reg No", H4)
        sheet_inv.write(8, 8, "Vehicle Model", H4)
        sheet_inv.write(8, 9, "Service Advisor", H4)
        sheet_inv.write(8, 10, "Business", H4)
        sheet_inv.write(8, 11, "Job Type", H4)
        sheet_inv.write(8, 12, "Invoice Line", H4)
        sheet_inv.write(8, 13, "Total Value", H4)
        sheet_inv.write(8, 14, "Gross Margin", H4)
        sheet_inv.write(8, 15, "Amount", H4)


        # # ##################################/////////////////////#####################################
        row = 9
        sr_number = 0
        for rec in record:
            account_move_invoices = self.env['account.move'].search([('id', '=', rec.task_id.id)], limit=1)
            sr_number += 1
            sheet_inv.write(row, 0, sr_number, H5)
            sheet_inv.write(row, 1, rec.lpo_no if rec.lpo_no else '', date_format)
            sheet_inv.write(row, 2, rec.move_id.name if rec.move_id else '', date_format)
            sheet_inv.write(row, 3, rec.move_id.invoice_date if rec.move_id else '', date_format)
            sheet_inv.write(row, 4, rec.move_id.partner_id.name if rec.move_id.partner_id else '', H5)
            sheet_inv.write(row, 5, rec.move_id.cc_job_card.name if rec.move_id.cc_job_card else '', H5)
            sheet_inv.write(row, 6, rec.odometer if rec.odometer else '', H5)
            sheet_inv.write(row, 7, rec.register_no, H5)
            sheet_inv.write(row, 8, rec.cc_vehicle_model.display_name if rec.task_id.cc_vehicle_model else '', H5)
            sheet_inv.write(row, 9, rec.user_ids[0].name if rec.user_ids else '', H5)
            sheet_inv.write(row, 10, rec.repair_category.name if rec.repair_category else '', H5)
            sheet_inv.write(row, 11, rec.repair_sub_category[0].name if rec.repair_sub_category else '', H5)
            sheet_inv.write(row, 12, rec.product_id.name if rec.product_id else '', H5)
            sheet_inv.write(row, 13, rec.total_sale_price if rec.total_sale_price else 0, H5)
            sheet_inv.write(row, 14, rec.computed_gross_margin if rec.computed_gross_margin else 0, H5)
            sheet_inv.write(row, 15, rec.price_subtotal if rec.price_subtotal else 0, H5)
            row += 1


        # ##########Adjusting column width######################
        sheet_inv.set_column(6, 0, 5)
        sheet_inv.set_column(6, 1, 12)
        sheet_inv.set_column(6, 7, 20)

        # # sheet.insert_image('A1', r'/opt/odoo13/custom_addons/ta_hrm/static/images/logo.png', {'x_scale': 0.5, 'y_scale': 0.5})
        sheet_inv.merge_range('E2:K4', "Invoice Report", H1)

        sheet_inv.write(5, 4, "From:", H3)
        sheet_inv.write(5, 9, "To:", H3)
        sheet_inv.write(5, 5, data.get('date_from'), date_format2)
        sheet_inv.write(5, 10, data.get('date_to'), date_format2)
        # # ________________________________________________________________________________
