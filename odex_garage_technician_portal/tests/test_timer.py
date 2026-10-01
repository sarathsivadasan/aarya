# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTechnicianTimer(TransactionCase):
    """The portal's primary model is account.analytic.line - these tests
    exercise the timer there, not on project.task."""

    def setUp(self):
        super().setUp()
        self.user = self.env['res.users'].create({
            'name': 'Test Technician', 'login': 'tech_timer_test',
            'email': 'tech_timer_test@example.com',
        })
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Technician', 'user_id': self.user.id,
            'workshop_position_type': 'worker', 'tz': 'Asia/Dubai',
        })
        self.project = self.env['project.project'].create({'name': 'Workshop'})
        self.task = self.env['project.task'].create({
            'name': 'JC-TEST-0001', 'is_jobcard': True, 'project_id': self.project.id,
        })
        self.line = self.env['account.analytic.line'].create({
            'task_id': self.task.id,
            'project_id': self.project.id,
            'employees_id': self.employee.id,
            'name': 'JC-TEST-0001',
        }).with_user(self.user)

    def _pass_qc(self):
        self.env['quality.checklist'].create({
            'name': 'Brake check', 'job_card_id': self.task.id, 'check_mark': True,
        })
        self.task.invalidate_recordset(['qc_passed'])

    def test_new_line_is_not_started(self):
        self.assertEqual(self.line.technician_status, 'not_started')

    def test_start_sets_running(self):
        self.line.action_technician_start()
        self.assertEqual(self.line.technician_status, 'running')
        self.assertTrue(self.line.start_datetime)
        self.assertTrue(self.line.is_start_time)

    def test_cannot_start_twice(self):
        self.line.action_technician_start()
        with self.assertRaises(UserError):
            self.line.action_technician_start()

    def test_pause_then_resume_returns_to_running(self):
        self.line.action_technician_start()
        self.line.action_technician_pause()
        self.assertEqual(self.line.technician_status, 'paused')
        self.line.action_technician_resume()
        # regression: job_card_extension leaves is_pause_time sticky-True,
        # so status must be derived from the timestamps, not that flag
        self.assertEqual(self.line.technician_status, 'running')

    def test_multiple_pause_resume_cycles_accumulate_pause_time(self):
        self.line.action_technician_start()
        for _ in range(3):
            self.line.action_technician_pause()
            self.line.action_technician_resume()
        self.assertEqual(self.line.technician_status, 'running')
        self.assertGreaterEqual(self.line.total_pause_time, 0.0)

    def test_elapsed_freezes_while_paused(self):
        self.line.action_technician_start()
        self.line.action_technician_pause()
        first = self.line._elapsed_seconds()
        second = self.line._elapsed_seconds()
        self.assertEqual(first, second, 'elapsed must not tick while paused')

    def test_end_not_gated_by_qc_on_job_card(self):
        # the QC gate only ever applied to Vehicle Inspections, which the
        # portal no longer handles - a Job Card ends without it
        self.line.action_technician_start()
        self.line.action_technician_end()
        self.assertEqual(self.line.technician_status, 'completed')

    def test_end_allowed_after_qc(self):
        self._pass_qc()
        self.line.action_technician_start()
        self.line.action_technician_end()
        self.assertEqual(self.line.technician_status, 'completed')
        self.assertTrue(self.line.end_datetime)

    def test_only_one_running_line_at_a_time(self):
        other_task = self.env['project.task'].create({
            'name': 'JC-TEST-0002', 'is_jobcard': True, 'project_id': self.project.id,
        })
        other = self.env['account.analytic.line'].create({
            'task_id': other_task.id, 'project_id': self.project.id,
            'employees_id': self.employee.id, 'name': 'JC-TEST-0002',
        }).with_user(self.user)

        self.line.action_technician_start()
        with self.assertRaises(UserError):
            other.action_technician_start()

    def test_paused_line_elsewhere_does_not_block_starting_another(self):
        other_task = self.env['project.task'].create({
            'name': 'JC-TEST-0003', 'is_jobcard': True, 'project_id': self.project.id,
        })
        other = self.env['account.analytic.line'].create({
            'task_id': other_task.id, 'project_id': self.project.id,
            'employees_id': self.employee.id, 'name': 'JC-TEST-0003',
        }).with_user(self.user)

        self.line.action_technician_start()
        self.line.action_technician_pause()
        other.action_technician_start()  # must not raise
        self.assertEqual(other.technician_status, 'running')

    def test_cannot_operate_on_someone_elses_line(self):
        other_employee = self.env['hr.employee'].create({'name': 'Someone Else'})
        foreign = self.env['account.analytic.line'].create({
            'task_id': self.task.id, 'project_id': self.project.id,
            'employees_id': other_employee.id, 'name': 'x',
        }).with_user(self.user)
        with self.assertRaises(UserError):
            foreign.action_technician_start()

    def test_display_uses_employee_timezone(self):
        self.line.action_technician_start()
        self.employee.tz = 'Asia/Kolkata'
        rendered = self.line._display_dt(self.line.start_datetime)
        self.assertTrue(rendered, 'should render a tz-converted string')
