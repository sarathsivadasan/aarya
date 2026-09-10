# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountMove(models.Model):
	_inherit = 'account.move'

	def action_post(self):
		res = super(AccountMove, self).action_post()
		if self.job_id:
			if self.job_id.sale_order_id and self.job_id.sale_order_id.inspection_id:
				if self.job_id.sale_order_id.inspection_id.gate_pass_id and self.job_id.sale_order_id.inspection_id.gate_pass_id.state == 'jobcard':
					self.job_id.sale_order_id.inspection_id.gate_pass_id.action_invoice()
		return res
