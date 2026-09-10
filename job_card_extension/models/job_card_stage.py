import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import ast


class JobCardStage(models.Model):
    _name = "job.card.stage"
    _description = "Job Card Stage"

    name = fields.Char(string="Name")
    value = fields.Char(string="Value")
    color = fields.Char(string="Color")
    project_task_id = fields.Many2one("project.task", string="Job Card")
    count_vehicle_in = fields.Integer(string="Vehicle In Count", compute="compute_stage_records")
    count_work_in_progress = fields.Integer(string="Work In Progress Count", compute="compute_stage_records")
    count_hold = fields.Integer(string="Hold Count", compute="compute_stage_records")
    count_no_action = fields.Integer(string="No Action Count", compute="compute_stage_records")
    count_awaiting_parts = fields.Integer(string="Waiting for Parts Count", compute="compute_stage_records")
    count_awaiting_approval = fields.Integer(string="Waiting for Approval Count", compute="compute_stage_records")
    count_ready = fields.Integer(string="Ready for Delivery Count", compute="compute_stage_records")
    count_delivered_not_invoiced = fields.Integer(string="Delivered not Invoiced Count",
                                                  compute="compute_stage_records")
    count_out = fields.Integer(string="Vehicle Out Count", compute="compute_stage_records")
    count_road_testing = fields.Integer(string="Road Testing Count", compute="compute_stage_records")
    count_washing = fields.Integer(string="Washing Count", compute="compute_stage_records")
    count_insurance = fields.Integer(string="Insurance Count", compute="compute_stage_records")
    count_closed = fields.Integer(string="Closed Job Count", compute="compute_stage_records")
    count_total = fields.Integer(string="Total Count", compute="compute_stage_records")

    def get_category_data(self):
        repair_category = self.env.user.repair_category
        repair_sub_category = self.env.user.repair_sub_category
        domain = []
        if repair_category and repair_sub_category:
            domain = [('repair_category', '=', repair_category.id),
                      ('repair_sub_category_ids', '=', repair_sub_category.id)]
        if repair_category and not repair_sub_category:
            domain = [('repair_category', '=', repair_category.id)]
        return domain

    def compute_stage_records(self):
        for rec in self:
            """
            Compute job card having state of Vehicle In
            """
            # repair_category=self.env.user.repair_category
            # repair_sub_category=self.env.user.repair_sub_category
            # domain=[]
            # if repair_category and repair_sub_category:
            #     domain=[('repair_category','=',repair_category.id),('repair_sub_category_ids','=',repair_sub_category.id)]
            # if repair_category and not repair_sub_category:
            #     domain=[('repair_category','=',repair_category.id)]
            domain = rec.get_category_data()

            # print([('is_jobcard', '=', True), ('cc_stage_value', '=', 'in')] + domain)
            rec.count_vehicle_in = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'in')] + domain)
            rec.count_work_in_progress = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'wip')] + domain)
            rec.count_hold = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'hold')] + domain)
            rec.count_no_action = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'no_action')] + domain)
            rec.count_awaiting_parts = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'awaiting_parts')] + domain)
            rec.count_awaiting_approval = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'awaiting_approval')] + domain)
            rec.count_ready = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'ready')] + domain)
            rec.count_delivered_not_invoiced = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'delivered_not_invoiced')] + domain)
            rec.count_out = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'out'),
                 ('date_end', '>=',
                  fields.Datetime.now().replace(hour=0, minute=0,
                                                second=0)),
                 ('date_end', '<=',
                  fields.Datetime.now().replace(hour=23, minute=59,
                                                second=59))] + domain)
            rec.count_road_testing = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'road_testing')] + domain)
            rec.count_washing = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'washing')] + domain)
            rec.count_insurance = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'insurance')] + domain)
            rec.count_closed = self.env['project.task'].search_count(
                [('is_jobcard', '=', True), ('cc_stage_value', '=', 'closed')] + domain)
            rec.count_total = self.env['project.task'].search_count([('is_jobcard', '=', True)] + domain)
            print('count_total',rec.count_total)

    def get_action_job_card_ready(self):
        """
        Get action of job card
        """
        action_obj = self.env["ir.actions.actions"]
        # Vehicle In
        if self.value == 'in':
            action = action_obj._for_xml_id('job_card_extension.open_vehicle_in_job_card')

        # Work In Progress
        if self.value == 'wip':
            action = action_obj._for_xml_id('job_card_extension.open_work_in_progress_job_card')

        # Hold
        if self.value == 'hold':
            action = action_obj._for_xml_id('job_card_extension.open_hold_job_card')

        # No Action
        if self.value == 'no_action':
            action = action_obj._for_xml_id('job_card_extension.open_no_action_job_card')

        # Waiting For Parts
        if self.value == 'awaiting_parts':
            action = action_obj._for_xml_id('job_card_extension.open_awaiting_parts_job_card')

        # Waiting For Approval
        if self.value == 'awaiting_approval':
            action = action_obj._for_xml_id('job_card_extension.open_awaiting_approval_job_card')

        # Ready For Delivery
        if self.value == 'ready':
            action = action_obj._for_xml_id('job_card_extension.open_ready_job_card')

        # Delivered Not Invoiced
        if self.value == 'delivered_not_invoiced':
            action = action_obj._for_xml_id('job_card_extension.open_delivered_not_invoiced_job_card')

        # Vehicle Out
        if self.value == 'out':
            action = action_obj._for_xml_id('job_card_extension.open_out_job_card')
            action['domain'] = [('is_jobcard', '=', True), ('cc_stage_value', '=', 'out'),
                                ('date_end', '>=', fields.Datetime.now().replace(hour=0, minute=0, second=0)),
                                ('date_end', '<=', fields.Datetime.now().replace(hour=23, minute=59, second=59))]

        # Road Testing
        if self.value == 'road_testing':
            action = action_obj._for_xml_id('job_card_extension.open_road_testing_job_card')

        # Washing
        if self.value == 'washing':
            action = action_obj._for_xml_id('job_card_extension.open_washing_job_card')

        # Insurance JobCard
        if self.value == 'insurance':
            action = action_obj._for_xml_id('job_card_extension.open_insurance_job_card')

        # Closed JobCard
        if self.value == 'closed':
            action = action_obj._for_xml_id('job_card_extension.open_closed_job_card')

        # Total
        if self.value == 'total':
            action = action_obj._for_xml_id('job_card_extension.open_total_job_card')

        if action:
            domain_list = ast.literal_eval(action['domain'])
            domain_list = domain_list + self.get_category_data()
            action['domain'] = str(domain_list)
            return action
        return True
