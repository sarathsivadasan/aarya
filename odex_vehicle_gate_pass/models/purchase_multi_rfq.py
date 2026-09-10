# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PurchaseMultiRFQ(models.Model):
    _inherit = 'purchase.multi.rfq'

    def action_award_line_wise(self): 
        res = super(PurchaseMultiRFQ, self).action_award_line_wise()
        if self.inspection_id:
            if self.inspection_id.gate_pass_id and self.inspection_id.gate_pass_id.state == 'inspection':
                self.inspection_id.gate_pass_id.action_rfq()
        return res