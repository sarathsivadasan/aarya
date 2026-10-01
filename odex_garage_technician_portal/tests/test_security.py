# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError
from odoo import fields


@tagged('post_install', '-at_install')
class TestTechnicianSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        tech_group = self.env.ref('odex_garage_technician_portal.group_garage_technician')

        self.user_a = self.env['res.users'].create({
            'name': 'Technician A', 'login': 'tech_sec_a', 'email': 'tech_sec_a@example.com',
            'groups_id': [(4, tech_group.id)],
        })
        self.user_b = self.env['res.users'].create({
            'name': 'Technician B', 'login': 'tech_sec_b', 'email': 'tech_sec_b@example.com',
            'groups_id': [(4, tech_group.id)],
        })
        self.employee_a = self.env['hr.employee'].create({
            'name': 'Employee A', 'user_id': self.user_a.id, 'workshop_position_type': 'worker',
        })
        self.employee_b = self.env['hr.employee'].create({
            'name': 'Employee B', 'user_id': self.user_b.id, 'workshop_position_type': 'worker',
        })
        # task_a: A is an assignee (user_ids)
        self.task_a = self.env['project.task'].create({
            'name': 'JC-SEC-A', 'is_jobcard': True, 'user_ids': [(4, self.user_a.id)],
        })
        # task_b: B is an assignee
        self.task_b = self.env['project.task'].create({
            'name': 'JC-SEC-B', 'is_jobcard': True, 'user_ids': [(4, self.user_b.id)],
        })

    def test_technician_sees_only_own_task(self):
        tasks = self.env['project.task'].with_user(self.user_a).search([('is_jobcard', '=', True)])
        self.assertIn(self.task_a.id, tasks.ids)
        self.assertNotIn(self.task_b.id, tasks.ids)

    def test_technician_cannot_read_other_task_directly(self):
        other_task = self.task_b.with_user(self.user_a)
        with self.assertRaises(AccessError):
            other_task.read(['name'])

    def test_technician_cannot_start_other_technicians_job(self):
        other_task = self.task_b.with_user(self.user_a)
        with self.assertRaises(AccessError):
            other_task.action_technician_start()

    def test_technician_with_own_timesheet_line_can_see_task_without_being_assignee(self):
        # task_c has neither A nor B as an assignee, but A has logged time on it
        task_c = self.env['project.task'].create({'name': 'JC-SEC-C', 'is_jobcard': True})
        self.env['account.analytic.line'].create({
            'task_id': task_c.id, 'employees_id': self.employee_a.id,
            'name': '/', 'date': fields.Date.today(),
        })
        tasks = self.env['project.task'].with_user(self.user_a).search([('is_jobcard', '=', True)])
        self.assertIn(task_c.id, tasks.ids)

    def test_non_portal_tasks_unaffected(self):
        # a plain project task (not a job card) must not
        # be filtered by the technician record rule at all
        plain_task = self.env['project.task'].create({'name': 'Plain Task'})
        tasks = self.env['project.task'].with_user(self.user_a).search([('id', '=', plain_task.id)])
        self.assertIn(plain_task.id, tasks.ids)
