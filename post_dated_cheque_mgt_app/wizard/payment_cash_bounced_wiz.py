# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class PaymentCashBouncedWiz(models.TransientModel):
	
	_name='payment.cash.bounced.wizard'
	_description = "Payment Cash Bounced"


	def payment_cash_bounced_records(self):
		for rec in self:
			pdc_account_payment_ids = self.env['pdc.account.payment'].browse(self._context.get('active_ids', []))
			if pdc_account_payment_ids:
				for payment in pdc_account_payment_ids:
					if payment.state != 'deposited':
						raise UserError(_("Only a Deposit pdc payment can be move to the Bounce State."))
					payment.cash_bounced_button()





