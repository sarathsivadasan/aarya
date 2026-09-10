# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PaymentCashReturndWiz(models.TransientModel):
	
	_name='payment.cash.returned.wizard'
	_description = "Payment Cash Returned"


	def payment_cash_returned_records(self):
		for rec in self:
			pdc_account_payment_ids = self.env['pdc.account.payment'].browse(self._context.get('active_ids', []))
			if pdc_account_payment_ids:
				for payment in pdc_account_payment_ids:
					if payment.state != 'collect_cash':
						raise UserError(_("Only a Collect Cheque pdc payment can be move to the Return State."))
					payment.cash_returned_button()