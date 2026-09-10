# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    journal_entry_id = fields.Many2one("account.move", string="Journal Entry", copy=False, tracking=True)
    

class JobCostSheet(models.Model):
    _inherit = "job.cost.sheet"

    qty_approve = fields.Float(string="Approved Quantity")
    request_sent = fields.Boolean(string="Part Request Sent")

    def create_jobcard_requisition(self):
        for each in self:
            jobcard_part_requisition = self.env['jobcard.part.requisition']
            found_jobcard_part_requisition = jobcard_part_requisition.search([('job_cost_sheet_id', '=', self.id)])
            if found_jobcard_part_requisition:
                raise UserError("Alredey Created Part Requisition.")
            new_jobcard_part_requisition = jobcard_part_requisition.create({
                'employee_id': self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1).id,
                'cost_type': self.cost_type,
                'product_id': self.product_id.id,
                'description': self.name,
                'qty': self.quantity,
                'uom_id': self.uom_id.id,
                'sale_price': self.price_unit,
                'company_id': self.task_id.company_id.id,
                'job_id': self.task_id.id,
                'register_no': self.task_id.vehicle_id.name,
                'cc_vehicle_model': self.task_id.model_id.id,
                'job_cost_sheet_id': self.id,
            })
            self.request_sent = True


