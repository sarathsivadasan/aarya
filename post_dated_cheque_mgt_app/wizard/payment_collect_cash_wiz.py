# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PaymentCollectCashWiz(models.TransientModel):
	
	_name='payment.collect.cash.wizard'
	_description = "Payment Collect Cheque"


	def payment_collect_cash_records(self):
		for rec in self:
			pdc_account_payment_ids = self.env['pdc.account.payment'].browse(self._context.get('active_ids', []))
			if pdc_account_payment_ids:
				for payment in pdc_account_payment_ids:
					if payment.state != 'draft':
						raise UserError(_("Only a Draft pdc payment can be move to the Colelct Cash State."))
					payment.write({'state': 'collect_cash'})