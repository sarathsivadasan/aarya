# -*- coding: utf-8 -*-

from odoo import fields, models, api


class JobRequestedService(models.Model):
    _name = 'job.requested.service'
    _description = "JOB REQUESTED SERVICE"

    # job_no = fields.Char(string="Job No", compute="compute_job_no", store=True)
    product_id = fields.Many2one('product.product', string='Service Requested', domain="[('type','=', 'service')]")
    assign_hours = fields.Float(string="Assign Hours")
    remark = fields.Char(string='Instruction')
    task_id = fields.Many2one('project.task', 'Task')
    is_added_in_timesheet = fields.Boolean("Is Added in Timesheet?")

    def add_service_to_timesheet_ext(self):
        for service in self:
            service_id = self.env['account.analytic.line'].create({
                'product_id': service.product_id.id,
                'name': service.remark,
                'assign_hours': service.assign_hours,
                'date': fields.Date.today(),
                'account_id': service.task_id.analytic_account_id.id,
            })
            service.task_id.job_card_daily_report_ids = [
                (4, service_id.id)
            ]
            service.is_added_in_timesheet = True

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.assign_hours = self.product_id.assign_hours
            self.remark = self.product_id.name
        else:
            self.assign_hours = ''
            self.remark = ''


# class JobWorkDescription(models.Model):
#     _name = 'job.work.description'

#     # job_no = fields.Char(string="Job No", compute="compute_job_no", store=True)
#     name = fields.Char(string='Work Description')
#     remark = fields.Char(string='Remarks')
#     task_id = fields.Many2one('project.task', 'Task')
