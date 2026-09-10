# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PaymentCashDepositdWiz(models.TransientModel):
	
	_name='payment.cash.deposit.wizard'
	_description = "Payment Cash Deposited"


	def payment_cash_deposit_records(self):
		for rec in self:
			pdc_account_payment_ids = self.env['pdc.account.payment'].browse(self._context.get('active_ids', []))
			if pdc_account_payment_ids:
				for payment in pdc_account_payment_ids:
					if payment.state not in ('collect_cash','returned','bounced'):
						raise UserError(_("Only a Collect Cheque, Return and Bounce pdc payment can be move to the Deposit State."))
					payment.cash_deposit_button()