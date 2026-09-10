# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PaymentCashCanceldWiz(models.TransientModel):
	
	_name='payment.cash.cancel.wizard'
	_description = "Payment Cash Cancelled"


	def payment_cash_cancel_records(self):
		for rec in self:
			pdc_account_payment_ids = self.env['pdc.account.payment'].browse(self._context.get('active_ids', []))
			if pdc_account_payment_ids:
				for payment in pdc_account_payment_ids:
					if payment.state not in ('collect_cash','returned','bounced'):
						raise UserError(_("Only a Collect Cheque, Return and Bounce pdc payment can be move to the Cancel State."))
					payment.action_invoice_cancel()