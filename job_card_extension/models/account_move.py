# -*- coding: utf-8 -*-
import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command
from num2words import num2words


class AccountMove(models.Model):
    _inherit = 'account.move'

    job_id = fields.Many2one("project.task", string="Job Card")
    vehicle_id = fields.Many2one("fleet.vehicle", string="License Plate")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="vehicle_id.vehicle_make_id",
                                   string="Vehicle Make")
    vehicle_model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    vehicle_color_id = fields.Many2one("vehicle.color", related="vehicle_id.color_id", string="Color")
    vin = fields.Char(string="Chassis No.", related="vehicle_id.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle_id.engin_no")
    year = fields.Selection(string="Year", related="vehicle_id.model_year")
    odometer = fields.Char(string="Odometer Reading")
    policy_no = fields.Char("Policy No.", related='job_id.policy_no')
    lpo_no = fields.Char("LPO No", related='job_id.lpo_no')
    lpo_date = fields.Date("LPO Date", related='job_id.lpo_date')
    claim_no = fields.Char("Claim No.", related='job_id.claim_no')
    insurance_company_id = fields.Many2one('res.partner', string='Insurance Company',
                                           related="job_id.insurance_company_id")
    pdc_payment_ids = fields.Many2many(
        'pdc.account.payment',
        compute='_compute_pdc_payment_ids',
        string='PDC Payments',
    )

    pdc_count = fields.Integer(
        compute='_compute_pdc_payment_ids'
    )

    def _compute_pdc_payment_ids(self):
        PDC = self.env['pdc.account.payment']
        pdcs = 0
        for move in self:
            if move.job_id:
                if move.job_id.customer_coupon_id:
                    pdcs = PDC.search([
                        ('coupon_id', '=', move.job_id.customer_coupon_id.id)
                    ])

                    move.pdc_payment_ids = pdcs
                    pdcs = len(pdcs)
            move.pdc_count = pdcs

    def action_view_pdc_payments(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('PDC Payments'),
            'res_model': 'pdc.account.payment',
            'view_mode': 'list,form',
            'domain': [('coupon_id', '=', self.job_id.customer_coupon_id.id)],
        }

    # @api.onchange('excess_amount')
    # def _onchange_excess_amount(self):
    #     for rec in self:
    #         if rec.job_id:
    #             print("rec.excess_amount,,,,,,,,,,", rec.excess_amount)
    #             excess_amount_product = rec.env['product.product'].search([('name', '=', 'Excess Amount')])
    #             if not excess_amount_product:
    #                 raise ValidationError("Excess Amount Product does not exist!")
    #             elif not excess_amount_product.property_account_expense_id or not excess_amount_product.property_account_income_id:
    #                 raise ValidationError("No Account has Selected on Excess Amount Product!")
    #
    #             config = rec.job_id.customer_coupon_id._get_accounting_config()
    #             unearned_account_id = config.get('unearned_revenue_account')
    #
    #             if  rec.job_id:
    #                 if rec.excess_amount >0 and not rec.job_id.use_coupon:
    #                     print("345345dsd")
    #                     line_ids = rec.invoice_line_ids = [(0, 0, {
    #                         'cost_type': "labour",
    #                         'product_id': excess_amount_product.id,  # Replace with a valid product ID
    #                         'name': excess_amount_product.name,
    #                         'quantity': 1.0,
    #                         'price_unit': rec.excess_amount * -1,  # Unit price
    #                         'partner_id': rec.partner_id.id,
    #                         'account_id': unearned_account_id,
    #                         'currency_id': rec.env.user.company_id.currency_id,
    #                         'tax_ids': excess_amount_product.taxes_id.ids,
    #                         # 'tax_ids': tax_on_partner.ids if tax_on_partner else excess_amount_product.taxes_id.ids,
    #                     })]
    #                     print("line_iddueeeds,,,,,,,,,,", line_ids)
    #                     rec._onchange_partner_id()
    #                     rec.cc_total_amount = rec.amount_untaxed
    #
    # @api.model
    # def default_get(self, fields_list):
    #     res = super().default_get(fields_list)
    #     print("werwerwrwerwerwerwersd")
    #     if res.get('job_id'):
    #         move = self.new(res)
    #         move._onchange_job_id()
    #         res.update(move._convert_to_write(move._cache))
    #
    #     return res

    @api.onchange('job_id')
    def _onchange_job_id(self):
        print("34234rdsfxvvvvvvxv")
        if self.job_id:
            print("34234rdsfffxvxv")
            cost_sheet_line_ids = self.job_id.job_cost_sheet_ids
            if self.job_id.vehicle_id:
                self.vehicle_id = self.job_id.vehicle_id.id
            if self.move_type in ['out_invoice','in_invoice', 'out_refund']:
                print("34234rdsfxvxv")
                if self.job_id.partner_id and not self.insurance_company_id:
                    if self.move_type == 'out_invoice':
                        self.partner_id = self.job_id.partner_id.id
                else:
                    if self.move_type == 'out_invoice':
                        self.partner_id = self.insurance_company_id.id
                    self.partner_excess_amount = self.job_id.partner_id.id
            if cost_sheet_line_ids and self.move_type in ['out_invoice','in_invoice','out_refund']:
                self.invoice_line_ids = [(5,0,0)]  # Clear existing invoice lines

                new_line_ids = self.env['account.move.line']
                for line in cost_sheet_line_ids: 
                    if line.invoice_checkbox == True:
                        print(",,,,,,,,,,")
                        vals = {
                            'product_id': line.product_id.id,
                            'name': line.product_id.name,
                            'quantity': line.quantity,
                            'product_uom_id': line.product_id.uom_id.id,
                            'price_unit': line.price_unit,
                            'account_id': line.account_id.id,
                            'analytic_distribution': {str(line.account_analytic_id.id): 100},
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'tax_ids': line.invoice_line_tax_ids,
                            'cost_type': line.cost_type,
                            'part_no': line.part_no,
                        }
                        print("vals,,,,,,,,,,", vals)
                        new_line_ids += self.env['account.move.line'].new(vals)
                # new_line_ids = self.env['account.move.line']

                # for line in cost_sheet_line_ids:
                #     vals = {
                #         'product_id': line.product_id.id,
                #         'name': line.product_id.name,
                #         'quantity': line.quantity,
                #         'product_uom_id': line.product_id.uom_id.id,
                #         'price_unit': line.price_unit,
                #         'account_id': line.account_id.id,
                #         'analytic_distribution': {str(line.account_analytic_id.id): 100},
                #         'currency_id': self.env.user.company_id.currency_id.id,
                #         'tax_ids': line.invoice_line_tax_ids,
                #         'cost_type': line.cost_type,
                #         'part_no': line.part_no,
                #     }
                #     new_line_ids += self.env['account.move.line'].new(vals)
                # print("98poyiukgjhmnvbassdf")
                self.invoice_line_ids += new_line_ids

    # def action_post(self):
    #     res = super().action_post()
    #
    #     for move in self.filtered(
    #             lambda m:
    #             m.move_type == 'out_invoice'
    #             and m.job_id
    #             and m.job_id.use_coupon
    #             and m.job_id.customer_coupon_id
    #     ):
    #         coupon = move.job_id.customer_coupon_id
    #         config = coupon._get_accounting_config()
    #
    #         unearned_account_id = config['unearned_revenue_account']
    #         if not unearned_account_id:
    #             continue
    #
    #         receivable_line = move.line_ids.filtered(
    #             lambda l:
    #             l.account_id.account_type == 'asset_receivable'
    #             and l.debit > 0
    #         )[:1]
    #
    #         if not receivable_line:
    #             continue
    #
    #         settlement_move = self.env['account.move'].create({
    #             'move_type': 'entry',
    #             'job_id': move.job_id.id,
    #             'journal_id': move.journal_id.id,
    #             'date': move.invoice_date or move.date,
    #             'ref': f'Coupon Settlement - {move.name}',
    #             'coupon_id': coupon.id,
    #             'line_ids': [
    #                 (0, 0, {
    #                     'account_id': unearned_account_id,
    #                     'debit': receivable_line.debit,
    #                     'credit': 0,
    #                     'partner_id': move.partner_id.id,
    #                 }),
    #                 (0, 0, {
    #                     'account_id': receivable_line.account_id.id,
    #                     'debit': 0,
    #                     'credit': receivable_line.debit,
    #                     'partner_id': move.partner_id.id,
    #                 }),
    #             ]
    #         })
    #
    #         settlement_move.action_post()
    #
    #         settlement_ar = settlement_move.line_ids.filtered(
    #             lambda l: l.account_id == receivable_line.account_id
    #         )
    #
    #         (receivable_line + settlement_ar).reconcile()
    #
    #     return res

    def separate_invoice_lines(self):
        """
        Separate invoice lines
        """
        invoice_cost_sheet_list = []
        labour = ''
        for rec in self:
            if rec.invoice_line_ids:
                for cost_type in set(rec.invoice_line_ids.mapped('cost_type')):
                    cost_sheet_list = []
                    if cost_type == 'labour':
                        labour = cost_type
                    else:
                        cost_sheet_list.append(rec.invoice_line_ids.filtered(lambda x: x.cost_type == cost_type))
                        invoice_cost_sheet_list.append(cost_sheet_list)
                print("34234234invoice_cost_sheet_list",invoice_cost_sheet_list)
                if labour:
                    invoice_cost_sheet_list.append(rec.invoice_line_ids.filtered(lambda x: x.cost_type == labour))    
        return invoice_cost_sheet_list


    def write_num2words(self, amount):
        # Split the amount into dollars and cents

        # Convert dollars and cents to words
        int_amount_word = int(amount)
        cents = int(amount % 1 * 100)

        if int_amount_word and cents:
            return f"{num2words(int_amount_word).replace('and', '').replace('thous', 'thousand').upper()} AND {num2words(cents).upper()} FILS"
        elif cents:
            return f"{num2words(cents).upper()} FILS"
        else:
            return num2words(amount).upper()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
    job_id = fields.Many2one("project.task", string="Job Card", related="move_id.job_id", store=True)

    @api.onchange('product_id')
    def _onchange_product_id_set_analytic(self):
        """Set analytic_distribution when product changes."""
        print("self.move_id...........", self.move_id)
        if not self.analytic_distribution:
            if self.product_id and self.move_id.job_id.analytic_account_id:
                self.analytic_distribution = {
                    self.move_id.job_id.analytic_account_id.id: 100
                }
        if self.product_id and self.move_id:
            self.vehicle_id = self.move_id.vehicle_id.id


   