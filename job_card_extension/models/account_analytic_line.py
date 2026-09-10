# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import pytz

def get_dubai_time():
    # Get the current time in UTC
    utc_now = datetime.utcnow()

    # Define the Dubai timezone
    dubai_tz = pytz.timezone('Asia/Dubai')

    # Convert UTC time to Dubai time
    dubai_time = utc_now.replace(tzinfo=pytz.utc).astimezone(dubai_tz)
    formated_time = dubai_time.time().strftime('%H:%M')
    # return formated_time
    return dubai_time.strftime("%Y-%m-%d %H:%M")

def datetime_to_string(datetime):
    # Use strptime to parse the string and convert it to a time object
    if datetime and type(datetime) == timedelta:
        return str(datetime)
    elif datetime:
        time_obj = datetime.time().strftime('%H:%M')
        return str(time_obj)
    return ''

def time_difference(start_datetime, end_datetime):
    # Calculate the time difference
    time_diff = end_datetime - start_datetime

    return time_diff

def add_times(datetime1, datetime2):
    # Add the datetime objects
    result_datetime = datetime1 + datetime2

    return result_datetime


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    user_id = fields.Many2one(
        'res.users',
        string="User",
        default=lambda self: self.env.user.id,
        readonly=True,
    )
    # job_card_payment_id = fields.Many2one('job.card.payment', string="Categories")
    assign_hours = fields.Float(string="Assign Hours", digits=(16, 2))
    start_datetime = fields.Datetime(string="Start Time")
    start_time = fields.Char(string="Start Time")
    display_start_time = fields.Char(string="Start Time")
    end_datetime = fields.Datetime(string="End Time")
    end_time = fields.Char(string="End Time")
    display_end_time = fields.Char(string="End Time")
    pause_datetime = fields.Datetime(string="Pause Time")
    pause_time = fields.Char(string="Pause Time")
    total_pause_time = fields.Float(string="Total Pause Time")
    resume_datetime = fields.Datetime(string="Resume Time")
    resume_time = fields.Char(string="Resume Time")
    is_start_time = fields.Boolean(string="Is start time?")
    is_pause_time = fields.Boolean(string="Is pause time?")
    is_resume_time = fields.Boolean(string="Is resume time?")
    is_end_time = fields.Boolean(string="Is start time?")
    total_hours = fields.Float(string="Total hours", compute="compute_total_hours", store=True)
    employees_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        required=False,
        domain="[('department_id', '=', departments_id)]"
    )
    employee_user_id = fields.Many2one(related="employees_id.user_id", string="Employee User")
    departments_id = fields.Many2one('hr.department', "Department")
    vehicle_id = fields.Many2one(related='task_id.vehicle_id', string="Vehicle", store=True)
    vehicle_model_id = fields.Many2one(related='task_id.model_id', string="Vehicle Model", store=True)
    user_ids = fields.Many2many(string="Assignees", related='task_id.user_ids')
    cc_stage_id = fields.Many2one('job.card.stage', string="Stage" ,related='task_id.cc_stage_id')

    @api.onchange('employees_id')
    def onchange_employees_id(self):
        for rec in self:
            print(rec.task_id, rec.employees_id)
            if rec.task_id and rec.employees_id != False:
                rec.task_id.cc_stage_id = 'wip'
                print('task_id')

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.unit_amount!=rec.total_hours:
                rec.unit_amount=rec.total_hours
            # if rec.instruction_job_id:
            #     timesheet_ids = self.search([('instruction_job_id', '=', rec.instruction_job_id.id)])
            #     instruction_id = self.env['instruction.job.order'].search([('id', '=', rec.instruction_job_id.id)])
            #     total_hours = 0.0
            #     if instruction_id:
            #         for timesheet in timesheet_ids:
            #             total_hours += timesheet.unit_amount
            #         instruction_id.total_hours = total_hours

        return res

    def action_start_time(self):
        """
        Action to add start time
        """
        for rec in self:
            rec.start_datetime = get_dubai_time()
            rec.start_time = datetime_to_string(rec.start_datetime)
            rec.is_start_time = True

    def action_pause_time(self):
        """
        Action to add pause time
        """
        for rec in self:
            rec.pause_datetime = get_dubai_time()
            rec.pause_time = datetime_to_string(rec.pause_datetime)
            rec.is_pause_time = True
            rec.is_resume_time = False

    # def action_resume_time(self):
    #     """
    #     Action to add resume time
    #     """
    #     for rec in self:
    #         rec.resume_datetime = get_dubai_time()
    #         timedelta = time_difference(rec.pause_datetime, rec.resume_datetime)
    #         rec.start_datetime = add_times(rec.start_datetime, timedelta)
    #         rec.start_time = datetime_to_string(rec.start_datetime)
    #         rec.is_resume_time = True
    #         rec.is_pause_time = False

    def action_resume_time(self):
        """
        Action to add resume time
        """
        for rec in self:
            rec.resume_datetime = get_dubai_time()
            rec.resume_time = datetime_to_string(rec.resume_datetime)
            print("pause_datetime,,,,,,,,,,,,,,", rec.pause_datetime, rec.pause_time)
            print("resume_datetime,,,,,,,,,,,,,,", rec.resume_datetime, rec.resume_time)
            # print("time_difference ,,,,,,,,,,,,", time_difference(rec.pause_time, rec.resume_time))
            # Calculate pause duration
            pause_duration = time_difference(rec.pause_datetime, rec.resume_datetime)
            print("pause_duration:", pause_duration)
            # Convert timedelta to minutes
            pause_minutes = pause_duration.total_seconds() / 3600.0
            print("pause_minutes:", pause_minutes)

            # Add to total pause time
            if not rec.total_pause_time:
                rec.total_pause_time = pause_minutes
            else:
                rec.total_pause_time += pause_minutes

            print("rec.total_pause_time:", rec.total_pause_time)
            # pause_duration = time_difference(rec.pause_datetime, rec.resume_datetime)
            # print("pause_duration,,,,,,,,,,,", pause_duration)

            # # Add to total pause time (initialize if None)
            # if not rec.total_pause_time:
            #     rec.total_pause_time = float((datetime_to_string(pause_duration)[:-3]).replace(":", "."))
            # else:
            #     rec.total_pause_time += float((datetime_to_string(pause_duration)[:-3]).replace(":", "."))
            # print("rec.total_pause_time,,,,,,,,,,,,,", rec.total_pause_time)

            # Adjust start time forward by pause duration
            # rec.start_datetime = add_times(rec.start_datetime, pause_duration)
            # rec.start_time = datetime_to_string(rec.start_datetime)

            rec.is_resume_time = True
            rec.is_pause_time = False

    def action_end_time(self):
        """
        Action to add start time
        """
        for rec in self:
            rec.end_datetime = get_dubai_time()
            rec.end_time = datetime_to_string(rec.end_datetime)
            rec.is_end_time = True

    @api.depends('start_datetime', 'end_datetime', 'total_pause_time')
    def compute_total_hours(self):
        """
        Compute total working hours minus pause time
        """
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                # Get total duration as timedelta
                total_duration = rec.end_datetime - rec.start_datetime

                # Convert to hours (float_time expects hours)
                total_hours = total_duration.total_seconds() / 3600.0

                # Subtract pause time (already stored in hours)
                rec.total_hours = total_hours - (rec.total_pause_time or 0.0)

                # Optional: round to nearest minute for cleaner display
                rec.total_hours = round(rec.total_hours, 4)  # 4 decimals ≈ 1 second precision

                # Debug prints
                print("total_duration:", total_duration)
                print("total_hours (raw):", total_hours)
                print("total_pause_time:", rec.total_pause_time)
                print("rec.total_hours:", rec.total_hours)

    @api.onchange("employees_id", "departments_id")
    def onchange_employees_id(self):
        for rec in self:
            if rec.employees_id:
                rec.user_id = rec.employee_user_id.id