# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ast import literal_eval


class JobCard(models.Model):
    _inherit = "project.task"

    def show_estimate_from_job_card(self):
        self.ensure_one()
        #        res = self.env.ref('account.action_invoice_tree1')
        res = self.env.ref('sale.action_quotations_with_onboarding')
        res = res.sudo().read()[0]
        res['context'] = str({'default_job_id': self.id,
                              # 'default_inspection_id': self.id,
                              'default_vehicle_id': self.vehicle_id.id if self.vehicle_id else None,
                              'default_partner_id': self.partner_id.id if self.partner_id else None,
                              'default_task_ids': [(4, self.id)]})

        res['domain'] = [
            '|',  '|',
            ('id', '=', self.sale_order_id.id),  ('job_id', '=', self.id),
            ('tasks_ids', 'in', [self.id])
        ]
        return res


class JobCostSheet(models.Model):
    _inherit = "job.cost.sheet"

    sale_estimate_id = fields.Many2one('sale.order')
    
