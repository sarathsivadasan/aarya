# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pdc_account_id = fields.Many2one('account.account', string="PDC Receivable Account",
                                     related='company_id.pdc_account_id', readonly=False)
    pdc_account_creditors_id = fields.Many2one('account.account', string="PDC Payable Account",
                                               related='company_id.pdc_account_creditors_id', readonly=False)

    customer_notify_check = fields.Boolean(string="Cheque Date Notification for Customer",
                                           related='company_id.customer_notify_check', readonly=False)
    vendor_notify_check = fields.Boolean(string="Cheque Date Notification for Vendor",
                                         related='company_id.vendor_notify_check', readonly=False)
    user_notify_check = fields.Boolean(string="Cheque Date Notification for User", related='company_id.user_notify_check',
                                       readonly=False)
    notify_opt_first = fields.Integer("Notify Before First Days", related='company_id.notify_opt_first', readonly=False)
    notify_opt_second = fields.Integer("Notify Before Second Days", related='company_id.notify_opt_second',
                                       readonly=False)
    notify_opt_thired = fields.Integer("Notify Before Third Days", related='company_id.notify_opt_thired',
                                       readonly=False)

    partner_ids = fields.Many2many('res.partner', 'res_config_cc_partner_rel', 'config_id', 'partner_id', "Customer",
                                   related='company_id.partner_ids', readonly=False,
                                   domain="[('customer_rank' ,'>', 0)]")
    ven_partner_ids = fields.Many2many('res.partner', 'ven_res_config_cc_ven_partner_rel', 'ven_config_id',
                                       'ven_partner_id', "Vendor", related='company_id.ven_partner_ids', readonly=False,
                                       domain="[('supplier_rank' ,'>', 0)]")
    post_user_ids = fields.Many2many('res.users', string='Users', related='company_id.post_user_ids', readonly=False)
