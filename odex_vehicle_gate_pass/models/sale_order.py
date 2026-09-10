# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        if self.inspection_id:
        	if self.inspection_id.gate_pass_id and self.inspection_id.gate_pass_id.state == 'purchase':
        		self.inspection_id.gate_pass_id.action_quotation()
        return res

    def create_job_card(self):
        result = super(SaleOrder, self).create_job_card()
        if self.inspection_id:
            if self.inspection_id.gate_pass_id and self.inspection_id.gate_pass_id.state == 'quotation':
                self.inspection_id.gate_pass_id.action_jobcard()
        return result

