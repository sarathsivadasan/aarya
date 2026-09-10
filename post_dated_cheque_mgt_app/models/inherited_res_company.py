# -*- coding: utf-8 -*-


from odoo import fields, models

class Company(models.Model):
	_inherit = 'res.company'

	pdc_account_id = fields.Many2one('account.account',string="PDC Receivable Account")
	pdc_account_creditors_id = fields.Many2one('account.account',string="PDC Payable Account")

	customer_notify_check = fields.Boolean('Customer Cheque Date Notification')
	vendor_notify_check = fields.Boolean('Vendor Cheque Date Notification')
	user_notify_check = fields.Boolean("User Cheque Date Notification")
	notify_opt_first = fields.Integer("Notify Before Days")
	notify_opt_second = fields.Integer("Notify Before Days")
	notify_opt_thired = fields.Integer("Notify Before Days")
	partner_ids = fields.Many2many('res.partner','res_config_cc_partner_rel', 'config_id', 'partner_id',"Customer", domain="[('customer_rank' ,'>', 0)]")
	ven_partner_ids = fields.Many2many('res.partner','ven_res_config_cc_ven_partner_rel', 'ven_config_id', 'ven_partner_id',"Vendor", domain="[('supplier_rank' ,'>', 0)]")    
	post_user_ids = fields.Many2many('res.users', string='Users')