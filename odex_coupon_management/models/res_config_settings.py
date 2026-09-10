# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Coupon Accounting Configuration
    coupon_unearned_revenue_account_id = fields.Many2one(
        'account.account',
        string='Unearned Revenue Account',
        config_parameter='odex_coupon.unearned_revenue_account',
        domain=[('account_type', 'in', ['liability_current', 'liability_non_current'])],
        help='Account for recording advance payments (Unearned Revenue / Deferred Revenue)',
    )
    coupon_sales_account_id = fields.Many2one(
        'account.account',
        string='Coupon Sales Account',
        config_parameter='odex_coupon.coupon_sales_account',
        help='Account for recognizing coupon revenue when service is rendered',
    )
    coupon_pdc_account_id = fields.Many2one(
        'account.account',
        string='PDC Account',
        config_parameter='odex_coupon.pdc_account',
        domain=[('account_type', 'in', ['asset_receivable', 'asset_current'])],
        help='Account for Post Dated Cheques Received',
    )
    coupon_invoice_account_id = fields.Many2one(
        'account.account',
        string='Invoice Account',
        config_parameter='odex_coupon.coupon_invoice_account_id',
        help='Account for Invoice',
    )
    coupon_default_journal_id = fields.Many2one(
        'account.journal',
        string='Default Journal',
        config_parameter='odex_coupon.default_journal',
        help='Default journal for coupon accounting entries',
    )
    coupon_vat_tax_id = fields.Many2one(
        'account.tax',
        string='VAT Tax',
        config_parameter='odex_coupon.vat_tax',
        domain=[('type_tax_use', '=', 'sale')],
        help='VAT tax applied on coupon revenue recognition',
    )
