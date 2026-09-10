# -*- encoding: utf-8 -*-
##############################################################################
#
#    Author: Codeware LLC
##############################################################################

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from datetime import date
import base64
import xlsxwriter
import xlsxwriter.utility
import io


class AccountVatReturnReport(models.TransientModel):
    _name = "account.vat.report"
    _description = "Account Vat Return Report"

    def _get_from_date(self):
        date2 = date(date.today().year, date.today().month - 3, 1)
        return date2

    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env.company)
    from_date = fields.Date('From', )
    to_date = fields.Date('To', )
    name = fields.Char('File Name', size=256, readonly=True)
    datas = fields.Binary('File', readonly=True)


    date_range_id = fields.Many2one('date.range', 'Date range', required=False)
    target_move = fields.Selection([
        ('posted', 'All Posted Entries'),
        ('all', 'All Entries'),
    ], 'Target Moves', required=True, default='posted')

    @api.onchange('date_range_id')
    def onchange_date_range_id(self):
        if self.date_range_id:
            self.from_date = self.date_range_id.date_start
            self.to_date = self.date_range_id.date_end
        else:
            self.from_date = time.strftime('%Y-%m-01')
            self.to_date = str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10]
            
    def _get_taxed_amounts_sale(self, journal_ids, tax_tags, tax_tags_return, tags, tags_return, company_id):
        vals = {}

        amount_value = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', tags), ('company_id', '=', company_id)])
        amount_value_return = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', tags_return), ('company_id', '=', company_id)])
        tax_value = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', tax_tags), ('company_id', '=', company_id)])
        tax_value_return = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', tax_tags_return), ('company_id', '=', company_id)])

        if tax_value:
            tax = ((sum(tax_value.mapped('amount_currency'))) + sum(tax_value_return.mapped('amount_currency')))
        else:
            tax = 0
        if amount_value:
            amount = ((sum(amount_value.mapped('amount_currency'))) + sum(
                amount_value_return.mapped('amount_currency')))
        else:
            amount = 0
        vals['amount'] = -amount
        vals['tax'] = -tax
        return vals
    
    def _get_taxed_amounts_purchase(self, journal_ids, purchase_tax_tags,
                                    _purchase_tax_tags_return, purchase_tags, purchase_tags_return, company_id):
        vals = {}

        amount_value = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', purchase_tags)])
        amount_value_return = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', purchase_tags_return),
             ('company_id', '=', company_id)])
        tax_value = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', purchase_tax_tags),
             ('company_id', '=', company_id)])
        tax_value_return = self.env["account.move.line"].search(
            [('id', 'in', journal_ids.ids), ('tax_tag_ids', 'in', _purchase_tax_tags_return),
             ('company_id', '=', company_id)])

        if tax_value:
            tax = (sum(tax_value.mapped('amount_currency'))) + sum(tax_value_return.mapped('amount_currency'))
        else:
            tax = 0
        if amount_value:
            amount = ((sum(amount_value.mapped('amount_currency')))) + sum(
                amount_value_return.mapped('amount_currency'))
        else:
            amount = 0
        vals['amount'] = amount
        vals['tax'] = tax
        return vals

    def generate_xlsx_report(self):
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        company_id = self.company_id.id
        company = self.env['res.company'].browse(company_id)
        to_date = self.to_date
        to_date1 = str(to_date)
        tax_year = to_date1[0:4]
        from_date = self.from_date
        datetimeobject = datetime.strptime(str(self.from_date), '%Y-%m-%d')
        start = datetimeobject.strftime('%d-%m-%Y')
        datetimeobject = datetime.strptime(str(self.to_date), '%Y-%m-%d')
        end = datetimeobject.strftime('%d-%m-%Y')
        vat_return_period = "From: " + str(start) + " To: " + str(end)
        format2 = workbook.add_format(
            {'font_size': 10, 'bg_color': '#E0FFFF', 'bold': True, 'font_name': 'Arial', 'border': True,
             'align': 'center', 'text_wrap': True})
        format4 = workbook.add_format(
            {'font_size': 10, 'bg_color': '#E0FFFF', 'bold': True, 'font_name': 'Arial', 'border': True,
             'align': 'left', 'text_wrap': True})
        format5 = workbook.add_format({'font_size': 10, 'font_name': 'Arial', 'border': True, 'align': 'right'})
        format6 = workbook.add_format(
            {'font_size': 10, 'bg_color': '#E0FFFF', 'bold': True, 'font_name': 'Arial', 'border': True,
             'align': 'right'})
        format7 = workbook.add_format(
            {'font_size': 10, 'bg_color': '#A9A9A9', 'bold': True, 'font_name': 'Arial', 'border': True,
             'align': 'right'})
        report_head = workbook.add_format({'font_size': 13, 'bold': True, 'font_color': '#000000', 'text_wrap': True, })
        report_format = workbook.add_format(
            {'font_size': 10, 'font_color': '#000000', 'border': True, 'text_wrap': True, })
        report_format_right = workbook.add_format(
            {'font_size': 10, 'align': 'right', 'font_color': '#000000', 'border': True, 'text_wrap': True, })

        h3 = workbook.add_format(
            {'align': 'center', 'bg_color': '#00205b', 'font_size': 10, 'bold': True, 'font_color': '#ffffff',
             'text_wrap': True, 'border': 1, })
        h4 = workbook.add_format(
            {'align': 'left', 'bg_color': '#00205b', 'font_size': 10, 'bold': True, 'font_color': '#ffffff',
             'text_wrap': True, 'border': 1, })

        h1 = workbook.add_format(
            {'align': 'center', 'bg_color': '#222222', 'font_size': 20, 'bold': True, 'font_color': '#ffffff'})

        sheet = workbook.add_worksheet("VAT 201- VAT Return")
        sheet.set_column('A:A', 60)
        sheet.set_column('B:B', 15)
        sheet.set_column('C:C', 15)
        sheet.set_column('D:D', 15)

        sheet.merge_range('A1:D2', "VAT 201 Report ", h1)
        sheet.write('A3', 'Taxable Person Details', format2)
        sheet.write('A4', 'TRN', format2)
        sheet.write('A5', company.vat, report_format)

        sheet.write('A6', 'Name', format2)
        sheet.write('A7', company.name, report_format)

        sheet.write('A8', 'VAT 201 Period', format2)
        sheet.write('A9', vat_return_period, report_format)

        sheet.merge_range('C8:D8', 'TAX Year', format2)
        sheet.merge_range('C9:D9', tax_year, report_format)

        sheet.merge_range('A11:D11', 'VAT on Sales and All Other Outputs', format2)
        sheet.write(11, 0, 'Name', format4)
        sheet.write(11, 1, 'Amount(AED)', format6)
        sheet.write(11, 2, 'VAT Amount(AED)', format6)
        sheet.write(11, 3, 'Adjustment(AED)', format6)
        row = 12

        journal_items = self.env['account.move.line'].sudo().search(
            [('display_type', 'not in', ('line_section', 'line_note')), ('move_id.date', '<=', to_date),
             ('move_id.date', '>=', from_date),
             ('move_id.state', '=', 'posted'), ('company_id', '=', company_id)])

        others_total1 = 0
        others_tax_total1 = 0
        others_untaxed_total1 = 0
        domain1 = [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date),
                   ('state', 'in', ['posted', 'paid']), ('company_id', '=', company_id)]
        SaleInvoices1 = self.env['account.move'].sudo().search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date),
             ('move_type', 'in', ('out_invoice', 'out_refund')),
             ('state', '=', 'posted'), ('company_id', '=', company_id)])
        PurchaseInvoices1 = self.env['account.move'].sudo().search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date), ('move_type', '=', 'in_invoice'),
             ('state', 'in', ['posted', 'paid']), ('company_id', '=', company_id)])
        if SaleInvoices1:
            domain1 = domain1 + [('id', 'not in', SaleInvoices1.ids)]
        if PurchaseInvoices1:
            domain1 = domain1 + [('id', 'not in', PurchaseInvoices1.ids)]
        OtherInvoices1 = self.env['account.move'].search(domain1)
        for other1 in OtherInvoices1:
            others_total1 += other1.amount_total_signed
            others_tax_total1 += other1.amount_tax_signed
            others_untaxed_total1 += other1.amount_untaxed
        
        tags_abudhabi = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+a. Abu Dhabi (Base)'])]).ids
        tags_abudhabi_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-a. Abu Dhabi (Base)'])]).ids
        tags_dubai = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+b. Dubai (Base)'])]).ids
        tags_dubai_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-b. Dubai (Base)'])]).ids
        tags_sharjah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+c. Sharjah (Base)'])]).ids
        tags_sharjah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-c. Sharjah (Base)'])]).ids
        tags_ajman = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+d. Ajman (Base)'])]).ids
        tags_ajman_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-d. Ajman (Base)'])]).ids
        tags_ummulquwain = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+e. Umm Al Quwain (Base)'])]).ids
        tags_ummulquwain_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-e. Umm Al Quwain (Base)'])]).ids
        tags_rasalkhaimah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+f. Ras Al-Khaima (Base)'])]).ids
        tags_rasalkhaimah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-f. Ras Al-Khaima (Base)'])]).ids
        tags_fujairah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+g. Fujairah (Base)'])]).ids
        tags_fujairah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-g. Fujairah (Base)'])]).ids
        tags_refunds_for_tourist_scheme = self.env['account.account.tag'].sudo().search(
            [('name', 'in',
              ['+2. Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme (Base)'])]).ids
        tags_refunds_for_tourist_scheme_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in',
              ['-2. Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme (Base)'])]).ids
        tags_reverse_charge_provisions = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+11. Supplies subject to the reverse charge provisions (Base)'])]).ids
        tags_reverse_charge_provisions_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-11. Supplies subject to the reverse charge provisions (Base)'])]).ids
        tags_zero_rated = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+4. Zero rated supplies (Base)'])]).ids
        tags_zero_rated_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-4. Zero rated supplies (Base)'])]).ids
        tags_exempted = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+5. Exempt supplies (Base)'])]).ids
        tags_exempted_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-5. Exempt supplies (Base)'])]).ids
        tags_imported_uae = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+7. Goods imported into the UAE (Base)'])]).ids
        tags_imported_uae_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-7. Goods imported into the UAE (Base)'])]).ids
        tags_adjustment_to_goods = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+8. Adjustment to goods (Base)'])]).ids
        tags_adjustment_to_goods_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-8. Adjustment to goods (Base)'])]).ids
        
        tax_tags_abudhabi = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+a. Abu Dhabi (Tax)'])]).ids
        tax_tags_abudhabi_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-a. Abu Dhabi (Tax)'])]).ids
        tax_tags_dubai = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+b. Dubai (Tax)'])]).ids
        tax_tags_dubai_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-b. Dubai (Tax)'])]).ids
        tax_tags_sharjah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+c. Sharjah (Tax)'])]).ids
        tax_tags_sharjah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-c. Sharjah (Tax)'])]).ids
        tax_tags_ajman = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+d. Ajman (Tax)'])]).ids
        tax_tags_ajman_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-d. Ajman (Tax)'])]).ids
        tax_tags_ummulquwain = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+e. Umm Al Quwain (Tax)'])]).ids
        tax_tags_ummulquwain_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-e. Umm Al Quwain (Tax)'])]).ids
        tax_tags_rasalkhaimah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+f. Ras Al-Khaima (Tax)'])]).ids
        tax_tags_rasalkhaimah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-f. Ras Al-Khaima (Tax)'])]).ids
        tax_tags_fujairah = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+g. Fujairah (Tax)'])]).ids
        tax_tags_fujairah_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-g. Fujairah (Tax)'])]).ids
        tax_tags_refunds_for_tourist_scheme = self.env['account.account.tag'].sudo().search(
            [('name', 'in',
              ['+2. Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme (Tax)'])]).ids
        tax_tags_refunds_for_tourist_scheme_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in',
              ['-2. Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme (Tax)'])]).ids
        tax_tags_reverse_charge_provisions = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+11. Supplies subject to the reverse charge provisions (Tax)'])]).ids
        tax_tags_reverse_charge_provisions_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-11. Supplies subject to the reverse charge provisions (Tax)'])]).ids
        tax_tags_zero_rated = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+4. Zero rated supplies (Tax)'])]).ids
        tax_tags_zero_rated_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-4. Zero rated supplies (Tax)'])]).ids
        tax_tags_exempted = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+5. Exempt supplies (Tax)'])]).ids
        tax_tags_exempted_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-5. Exempt supplies (Tax)'])]).ids
        tax_tags_imported_uae = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+7. Goods imported into the UAE (Tax)'])]).ids
        tax_tags_imported_uae_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-7. Goods imported into the UAE (Tax)'])]).ids
        tax_tags_adjustment_to_goods = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+8. Adjustment to goods (Tax)'])]).ids
        tax_tags_adjustment_to_goods_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-8. Adjustment to goods (Tax)'])]).ids

        total_sale = 0
        total_vat = 0
        sheet.write(row, 0, '1a  Standard rated supplies in Abudhabi', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_abudhabi,
                                                     tax_tags_abudhabi_return,
                                                     tags_abudhabi, tags_abudhabi_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')

        row += 1

        sheet.write(row, 0, '1b  Standard rated supplies in Dubai', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_dubai, tax_tags_dubai_return, tags_dubai,
                                                     tags_dubai_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '1c Standard rated supplies in Sharjah', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_sharjah, tax_tags_sharjah_return,
                                                     tags_sharjah, tags_sharjah_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '1d  Standard rated supplies in Ajman', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_ajman, tax_tags_ajman_return, tags_ajman,
                                                     tags_ajman_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '1e  Standard rated supplies in Umm Al Quwain', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_ummulquwain,
                                                     tax_tags_ummulquwain_return, tags_ummulquwain,
                                                     tags_ummulquwain_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '1f  Standard rated supplies in Ras Al-Khaimah', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_rasalkhaimah,
                                                     tax_tags_rasalkhaimah_return,
                                                     tags_rasalkhaimah, tags_rasalkhaimah_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '1g  Standard rated supplies in Fujairah', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_fujairah, tax_tags_fujairah_return,
                                                     tags_fujairah, tags_fujairah_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '2  Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme',
                    report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, \
                                                    tax_tags_refunds_for_tourist_scheme,\
                                                    tax_tags_refunds_for_tourist_scheme_return, \
                                                    tags_refunds_for_tourist_scheme, \
                                                    tags_refunds_for_tourist_scheme_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '3  Supplies subject to the reverse charge provisions', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items,\
                                                    tax_tags_reverse_charge_provisions,\
                                                    tax_tags_reverse_charge_provisions_return, \
                                                    tags_reverse_charge_provisions, \
                                                    tags_reverse_charge_provisions_return,company_id)
        sheet.write(row, 1, -(taxed_amounts.get('amount')), report_format)
        sheet.write(row, 2, -(taxed_amounts.get('tax')), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale -(taxed_amounts.get('amount'))
        total_vat = total_vat -(taxed_amounts.get('tax'))
        row += 1

        sheet.write(row, 0, '4  Zero rated supplies', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_zero_rated,
                                                     tax_tags_zero_rated_return,
                                                     tags_zero_rated, tags_zero_rated_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '5  Exempt supplies', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_exempted,
                                                     tax_tags_exempted_return,
                                                     tags_exempted, tags_exempted_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '6  Goods imported into the UAE*', report_format)
        taxed_amounts = self._get_taxed_amounts_sale(journal_items, tax_tags_imported_uae,
                                                     tax_tags_imported_uae_return, tags_imported_uae,
                                                     tags_imported_uae_return, company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')

        row += 1
        sheet.write(row, 0, '7  Adjustments to goods imported into the UAE*', report_format)
        sheet.write(row, 1, 0, format5)
        sheet.write(row, 2, 0, format5)
        sheet.write(row, 3, "-", format5)
        sheet.write(row, 5, "<= Manual to be calculated from customs charges", format5)
        total_sale = total_sale + taxed_amounts.get('amount')
        total_vat = total_vat + taxed_amounts.get('tax')
        row += 1

        sheet.write(row, 0, '8  Total', format4)
        sheet.write(row, 1, total_sale, report_format)
        sheet.write(row, 2, total_vat, report_format)
        sheet.write(row, 3, '', format7)

        row += 3

        sheet.merge_range('A28:D28', 'VAT on Expenses and All Other Inputs', format2)

        sheet.write(row, 0, 'Standard rated expenses', format4)
        sheet.write(row, 1, 'Amount(AED)', format6)
        sheet.write(row, 2, 'VAT Amount(AED)', format6)
        sheet.write(row, 3, 'Adjustment(AED)', format6)
        row += 1

        tags_standard_rate_expense_purchase = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+10. Standard rated expenses (Base)'])]).ids
        tags_standard_rate_expense_purchase_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-10. Standard rated expenses (Base)'])]).ids
        tax_tags_standard_rate_expense_purchase = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+10. Standard rated expenses (Tax)'])]).ids
        tax_tags_standard_rate_expense_purchase_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-10. Standard rated expenses (Tax)'])]).ids
        tags_reverse_charge_purchase = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+11. Supplies subject to the reverse charge provisions (Base)'])]).ids
        tags_reverse_charge_purchase_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-11. Supplies subject to the reverse charge provisions (Base)'])]).ids
        tax_tags_reverse_charge_purchase = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['+11. Supplies subject to the reverse charge provisions (Tax)'])]).ids
        tax_tags_reverse_charge_purchase_return = self.env['account.account.tag'].sudo().search(
            [('name', 'in', ['-11. Supplies subject to the reverse charge provisions (Tax)'])]).ids
        
        total_purchase = 0
        total_purchase_vat = 0

        sheet.write(row, 0, '9 Standard Rated Expenses', report_format)
        taxed_amounts = self._get_taxed_amounts_purchase(journal_items, tax_tags_standard_rate_expense_purchase , \
                                                        tax_tags_standard_rate_expense_purchase_return ,\
                                                        tags_standard_rate_expense_purchase, tags_standard_rate_expense_purchase_return, 
                                                        company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_purchase = total_purchase + taxed_amounts.get('amount')
        total_purchase_vat = total_purchase_vat + taxed_amounts.get('tax')
        row += 1
        sheet.write(row, 0, '10  Supplies subject to the reverse charge provisions', report_format)
        taxed_amounts = self._get_taxed_amounts_purchase(journal_items, tax_tags_reverse_charge_purchase , \
                                                         tax_tags_reverse_charge_purchase_return ,\
                                                         tags_reverse_charge_purchase,
                                                         tags_reverse_charge_purchase_return,
                                                         company_id)
        sheet.write(row, 1, taxed_amounts.get('amount'), report_format)
        sheet.write(row, 2, taxed_amounts.get('tax'), report_format)
        sheet.write(row, 3, "-", format5)
        total_purchase = total_purchase + taxed_amounts.get('amount')
        total_purchase_vat = total_purchase_vat + taxed_amounts.get('tax')
        row += 1
        row += 1
        sheet.write(row, 0, '11  Totals', format4)
        sheet.write(row, 1, total_purchase, format7)
        sheet.write(row, 2, total_purchase_vat, format7)
        sheet.write(row, 3, 0, format7)

        sheet.merge_range('A34:D34', 'NET VAT Due', h4)

        row += 3
        sheet.write(row, 0, '12  Total value of due tax for the period', format4)
        sheet.write(row, 1, total_vat, format7)

        row += 1
        sheet.write(row, 0, '13  Total value of recoverable tax for the period', format4)
        sheet.write(row, 1, total_purchase_vat, format7)

        row += 1
        sheet.write(row, 0, '14  Payable Tax for the period', format4)
        sheet.write(row, 1, total_vat - total_purchase_vat, format7)

        sheet1 = workbook.add_worksheet(str("Sales"))
        sheet1.set_default_row(25)
        sheet1.set_column('A:A', 20)
        sheet1.set_column('B:B', 35)
        sheet1.set_column('C3:C3', 25)
        sheet1.set_column('D3:D3', 20)
        sheet1.set_column('E3:E3', 20)
        row = 1
        sheet1.write(row, 2, 'Sales  Report', report_head)
        row += 1
        sheet1.write(row, 0, 'Customer', h3)
        sheet1.write(row, 1, 'Invoice Date', h3)
        sheet1.write(row, 2, 'Number', h3)
        sheet1.write(row, 3, 'Untax Amount', h3)
        sheet1.write(row, 4, 'Tax Amount ', h3)
        sheet1.write(row, 5, 'Amount ', h3)
        sale_total = 0
        sale_total_tax = 0
        sale_untax_total = 0
        SaleInvoices = self.env['account.move'].sudo().search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date),
             ('move_type', '=', 'out_invoice'),
             ('state', '=', 'posted'), ('company_id', '=', company_id)])

        row += 1

        for saleobj in SaleInvoices:
            tax = saleobj.amount_tax_signed
            subtotal = saleobj.amount_untaxed_signed
            total = saleobj.amount_total_signed
            datetimeobject = datetime.strptime(str(saleobj.invoice_date), '%Y-%m-%d')
            invoice_date = datetimeobject.strftime('%d-%m-%Y')
            sheet1.write(row, 0, saleobj.partner_id.name, report_format)
            sheet1.write(row, 1, str(invoice_date), report_format)
            sheet1.write(row, 2, saleobj.name, report_format)
            sheet1.write(row, 3, "{:.2f}".format(subtotal), report_format_right)
            sheet1.write(row, 4, "{:.2f}".format(tax), report_format_right)
            sheet1.write(row, 5, "{:.2f}".format(total), report_format_right)

            sale_total += total
            sale_total_tax += tax
            sale_untax_total += subtotal
            row += 1
        sheet1.write(row, 0, 'Total', h3)
        sheet1.write(row, 3, "{:.2f}".format(sale_untax_total), format7)
        sheet1.write(row, 4, "{:.2f}".format(sale_total_tax), format7)
        sheet1.write(row, 5, "{:.2f}".format(sale_total), format7)

        row += 2

        sheet1.write(row, 2, 'Credit Notes', report_head)

        credit_note_total = 0
        credit_note_total_tax = 0
        credit_note_untax_total = 0
        CreditNotes = self.env['account.move'].sudo().search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date),
             ('move_type', '=', 'out_refund'),
             ('state', '=', 'posted'), ('company_id', '=', company_id)])
        row += 1
        for credit_note in CreditNotes:
            tax = credit_note.amount_tax_signed
            subtotal = credit_note.amount_untaxed_signed
            total = credit_note.amount_total_signed
            datetimeobject = datetime.strptime(str(credit_note.invoice_date), '%Y-%m-%d')
            invoice_date = datetimeobject.strftime('%d-%m-%Y')
            sheet1.write(row, 0, credit_note.partner_id.name, report_format)
            sheet1.write(row, 1, str(invoice_date), report_format)
            sheet1.write(row, 2, credit_note.name, report_format)
            sheet1.write(row, 3, "{:.2f}".format(subtotal), report_format_right)
            sheet1.write(row, 4, "{:.2f}".format(tax), report_format_right)
            sheet1.write(row, 5, "{:.2f}".format(total), report_format_right)

            credit_note_total += total
            credit_note_total_tax += tax
            credit_note_untax_total += subtotal
            row += 1
        sheet1.write(row, 0, 'Total', h3)
        sheet1.write(row, 3, "{:.2f}".format(credit_note_untax_total), format7)
        sheet1.write(row, 4, "{:.2f}".format(credit_note_total_tax), format7)
        sheet1.write(row, 5, "{:.2f}".format(credit_note_total), format7)
        sheet2 = workbook.add_worksheet(str("Purchase"))
        sheet2.set_default_row(25)
        sheet2.set_column('A:A', 20)
        sheet2.set_column('B:B', 35)
        sheet2.set_column('C3:C3', 25)
        sheet2.set_column('D3:D3', 20)
        sheet2.set_column('E3:E3', 20)
        row = 1
        sheet2.write(row, 2, 'Purchase  Report', report_head)
        row += 1
        sheet2.write(row, 0, 'Vendor', h3)
        sheet2.write(row, 1, 'Invoice Date', h3)
        sheet2.write(row, 2, 'Number', h3)
        sheet2.write(row, 3, 'Untax Amount', h3)
        sheet2.write(row, 4, 'Tax Amount ', h3)
        sheet2.write(row, 5, 'Amount', h3)
        purchase_total = 0
        purchase_total_tax = 0
        purchase_untax_total = 0
        row += 1
        PurchaseInvoices = self.env['account.move'].sudo().search(
            [('date', '>=', from_date), ('date', '<=', to_date), ('move_type', '=', 'in_invoice'),
             ('state', 'in', ['posted', 'paid']), ('company_id', '=', company_id)])
        for purchase in PurchaseInvoices:
            tax = purchase.amount_tax_signed
            subtotal = purchase.amount_untaxed_signed
            total = purchase.amount_total_signed
            datetimeobject = datetime.strptime(str(purchase.invoice_date), '%Y-%m-%d')
            invoice_date = datetimeobject.strftime('%d-%m-%Y')
            sheet2.write(row, 0, purchase.partner_id.name, report_format)
            sheet2.write(row, 1, str(invoice_date), report_format)
            sheet2.write(row, 2, purchase.name, report_format)
            sheet2.write(row, 3, "{:.2f}".format(subtotal), report_format_right)
            sheet2.write(row, 4, "{:.2f}".format(tax), report_format_right)
            sheet2.write(row, 5, "{:.2f}".format(total), report_format_right)
            purchase_untax_total += subtotal
            purchase_total_tax += tax
            purchase_total += total
            row += 1
        sheet2.write(row, 0, 'Total', h3)
        sheet2.write(row, 3, "{:.2f}".format(purchase_untax_total), format7)
        sheet2.write(row, 4, "{:.2f}".format(purchase_total_tax), format7)
        sheet2.write(row, 5, "{:.2f}".format(purchase_total), format7)
        row += 2
        sheet2.write(row, 2, 'Refunds', report_head)
        refund_total = 0
        refund_total_tax = 0
        refund_untax_total = 0
        Refunds = self.env['account.move'].sudo().search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date),
             ('move_type', '=', 'in_refund'),
             ('state', '=', 'posted'), ('company_id', '=', company_id)])
        row += 1
        for refund in Refunds:
            tax = refund.amount_tax_signed
            subtotal = refund.amount_untaxed_signed
            total = refund.amount_total_signed
            datetimeobject = datetime.strptime(str(refund.invoice_date), '%Y-%m-%d')
            invoice_date = datetimeobject.strftime('%d-%m-%Y')
            sheet2.write(row, 0, refund.partner_id.name, report_format)
            sheet2.write(row, 1, str(invoice_date), report_format)
            sheet2.write(row, 2, refund.name, report_format)
            sheet2.write(row, 3, "{:.2f}".format(subtotal), report_format_right)
            sheet2.write(row, 4, "{:.2f}".format(tax), report_format_right)
            sheet2.write(row, 5, "{:.2f}".format(total), report_format_right)
            refund_total += total
            refund_total_tax += tax
            refund_untax_total += subtotal
            row += 1
        sheet2.write(row, 0, 'Total', h3)
        sheet2.write(row, 3, "{:.2f}".format(refund_untax_total), format7)
        sheet2.write(row, 4, "{:.2f}".format(refund_total_tax), format7)
        sheet2.write(row, 5, "{:.2f}".format(refund_total), format7)

        # Others
        sheet3 = workbook.add_worksheet(str("Other Voucher"))
        sheet3.set_default_row(25)
        sheet3.set_column('A:A', 20)
        sheet3.set_column('B:B', 35)
        sheet3.set_column('C3:C3', 25)
        sheet3.set_column('D3:D3', 20)
        sheet3.set_column('E3:E3', 20)
        row = 1
        sheet3.write(row, 2, 'Other Voucher  Report', report_head)
        row += 1
        sheet3.write(row, 0, 'Partner', h3)
        sheet3.write(row, 1, 'Invoice Date', h3)
        sheet3.write(row, 2, 'Number', h3)
        sheet3.write(row, 3, 'Untax Amount', h3)
        sheet3.write(row, 4, 'Tax Amount ', h3)
        sheet3.write(row, 5, 'Amount ', h3)
        
        row += 1
        move_line_ids = self.env['account.move.line'].sudo().search(
            [('date', '>=', from_date), ('date', '<=', to_date),
             ('move_id.state', '=', 'posted'), ('company_id', '=', company_id),
             ('tax_tag_ids.name','=','+10. Standard rated expenses (Tax)'),
             ('journal_id.name','=','Miscellaneous Operations')])
        total_base_amount = 0
        total_vat_amount = 0
        total_amount = 0
        for line in move_line_ids:
            sheet3.write(row, 0, line.move_id.partner_id.name if line.move_id.partner_id.name else '', report_format)
            datetimeobject = datetime.strptime(str(line.date), '%Y-%m-%d')
            date = datetimeobject.strftime('%d-%m-%Y')
            sheet3.write(row, 1, date, report_format)
            sheet3.write(row, 2, line.move_id.name, report_format)
            sheet3.write(row, 3, line.tax_base_amount, report_format_right)
            sheet3.write(row, 4, line.amount_currency, report_format_right)
            sheet3.write(row, 5, line.tax_base_amount + line.amount_currency, report_format_right)
            total_base_amount += line.tax_base_amount
            total_vat_amount += line.amount_currency
            total_amount += (line.tax_base_amount + line.amount_currency)
            row += 1
        sheet3.write(row, 0, 'Total', h3)
        sheet3.write(row, 3, "{:.2f}".format(total_base_amount), format7)
        sheet3.write(row, 4, "{:.2f}".format(total_vat_amount), format7)
        sheet3.write(row, 5, "{:.2f}".format(total_amount), format7)
        workbook.close()
        out = base64.encodebytes(fp.getvalue())
        report_name = 'VAT 201 Report'
        filename = '%s'%(report_name)
        self.write({'datas': out, 'name': filename})
        fp.close()
        filename += '%2Exlsx'

        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': 'web/content/?model='+self._name+'&id='+str(self.id)+'&field=datas&download=true&filename='+filename,
        }
