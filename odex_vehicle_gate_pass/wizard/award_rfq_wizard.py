# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

class AwardRFQWizard(models.TransientModel):
    _inherit = 'award.rfq.wizard'

    def action_award(self):
    	res = super(AwardRFQWizard, self).action_award()
    	if self.multi_rfq_id.inspection_id:
    		if self.multi_rfq_id.inspection_id.gate_pass_id and self.multi_rfq_id.inspection_id.gate_pass_id.state == 'rfq':
    			self.multi_rfq_id.inspection_id.gate_pass_id.action_purchase()
    	return res