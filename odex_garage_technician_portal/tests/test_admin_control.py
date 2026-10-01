# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAdministratorControl(TransactionCase):
    """Requirement 3 + 4: an administrator sees every assigned job card,
    can pause/resume/stop it, and every action is logged with
    the job reference, technician, action, timestamp and acting user."""

    def setUp(self):
        super().setUp()
        self.tech_user = self.env['res.users'].create({
            'name': 'Tech A', 'login': 'tech_admin_test',
            'email': 'tech_admin_test@example.com',
            'groups_id': [(4, self.env.ref(
                'odex_garage_technician_portal.group_garage_technician').id)],
        })
        self.tech = self.env['hr.employee'].create({
            'name': 'Tech A', 'user_id': self.tech_user.id, 'tz': 'Asia/Dubai',
        })
        self.admin_user = self.env['res.users'].create({
            'name': 'Supervisor', 'login': 'sup_admin_test',
            'email': 'sup_admin_test@example.com',
            'groups_id': [(4, self.env.ref(
                'odex_garage_technician_portal.group_garage_technician_supervisor').id)],
        })
        self.project = self.env['project.project'].create({'name': 'Workshop'})
        self.jobcard = self.env['project.task'].create({
            'name': 'JC-ADM-0001', 'is_jobcard': True, 'project_id': self.project.id,
        })
        self.jc_line = self.env['account.analytic.line'].create({
            'task_id': self.jobcard.id, 'project_id': self.project.id,
            'employees_id': self.tech.id, 'name': 'JC-ADM-0001',
        })
        self.plain_task = self.env['project.task'].create({
            'name': 'PLAIN-ADM-0001', 'project_id': self.project.id,
        })
        self.plain_line = self.env['account.analytic.line'].create({
            'task_id': self.plain_task.id, 'project_id': self.project.id,
            'employees_id': self.tech.id, 'name': 'PLAIN-ADM-0001',
        })

    def _logs(self, line):
        return self.env['technician.log'].search([
            ('analytic_line_id', '=', line.id)], order='id')

    # ------------------------------------------------------------------
    # visibility
    # ------------------------------------------------------------------
    def test_admin_query_lists_job_cards_only(self):
        AAL = self.env['account.analytic.line']
        lines = AAL.search(AAL._all_lines_domain())
        self.assertIn(self.jc_line, lines, 'Job Card work must be listed')
        self.assertNotIn(self.plain_line, lines,
                         'work on non-job-card tasks must not be listed')

    def test_admin_list_item_names_technician_and_status(self):
        self.jc_line.action_admin_start()
        data = self.jc_line.to_admin_list_item()
        self.assertEqual(data['technician'], self.tech.display_name)
        self.assertEqual(data['status'], 'running')
        self.assertEqual(data['record_type'], 'job_card')

    def test_supervisor_can_read_another_technicians_line(self):
        # the supervisor group implies the technician group, whose record
        # rule limits reads to own lines; the companion supervisor rule
        # must restore the full view
        as_admin = self.jc_line.with_user(self.admin_user)
        self.assertTrue(as_admin.read(['id']),
                        'supervisor must be able to read other technicians work')

    # ------------------------------------------------------------------
    # control
    # ------------------------------------------------------------------
    def test_admin_pause_resume_stop_moves_status_and_time(self):
        line = self.jc_line
        line.action_admin_start()
        self.assertEqual(line.technician_status, 'running')
        line.action_admin_pause()
        self.assertEqual(line.technician_status, 'paused')
        self.assertTrue(line.pause_datetime)
        line.action_admin_resume()
        self.assertEqual(line.technician_status, 'running')
        self.assertTrue(line.resume_datetime)
        line.action_admin_end()
        self.assertEqual(line.technician_status, 'completed')
        self.assertTrue(line.end_datetime)

    def test_non_admin_cannot_drive_another_technicians_timer(self):
        other_user = self.env['res.users'].create({
            'name': 'Tech B', 'login': 'tech_b_admin_test',
            'email': 'tech_b_admin_test@example.com',
            'groups_id': [(4, self.env.ref(
                'odex_garage_technician_portal.group_garage_technician').id)],
        })
        self.env['hr.employee'].create({'name': 'Tech B', 'user_id': other_user.id})
        with self.assertRaises(UserError):
            self.jc_line.with_user(other_user).action_admin_pause()

    def test_admin_end_excludes_paused_time(self):
        line = self.jc_line
        line.action_admin_start()
        line.action_admin_pause()
        line.action_admin_resume()
        line.action_admin_end()
        gross = (line.end_datetime - line.start_datetime).total_seconds() / 3600.0
        self.assertAlmostEqual(
            line.technician_net_hours, gross - line.total_pause_time, places=4,
            msg='net working hours must exclude the accumulated pause time')

    # ------------------------------------------------------------------
    # audit log
    # ------------------------------------------------------------------
    def test_every_action_is_logged_with_the_required_fields(self):
        line = self.jc_line.with_user(self.admin_user)
        line.action_admin_start()
        line.action_admin_pause()
        line.action_admin_resume()
        line.action_admin_end()
        logs = self._logs(self.jc_line)
        self.assertEqual(
            logs.mapped('action'), ['started', 'paused', 'resumed', 'completed'])
        for log in logs:
            self.assertEqual(log.job_reference, 'JC-ADM-0001', 'job reference')
            self.assertEqual(log.technician_id, self.tech, 'technician')
            self.assertEqual(log.user_id, self.admin_user, 'acting user')
            self.assertTrue(log.log_date, 'date and time')
            self.assertTrue(log.is_admin_action, 'flagged as an admin action')
            self.assertEqual(log.record_type, 'job_card')

    def test_technician_actions_are_not_flagged_as_admin(self):
        line = self.jc_line.with_user(self.tech_user)
        line.action_technician_start()
        line.action_technician_pause()
        logs = self._logs(self.jc_line)
        self.assertTrue(logs)
        self.assertFalse(any(logs.mapped('is_admin_action')))
        self.assertEqual(logs.mapped('user_id'), self.tech_user)


@tagged('post_install', '-at_install')
class TestJobStatusRollup(TransactionCase):
    """v4.0.0: the PDF report printed `my_timer_status`, which was never
    declared - printing raised. These cover the real rollup field that
    replaced it."""

    def setUp(self):
        super().setUp()
        self.project = self.env['project.project'].create({'name': 'Workshop'})
        self.task = self.env['project.task'].create({
            'name': 'JC-ROLL-0001', 'is_jobcard': True, 'project_id': self.project.id,
        })
        self.tech_a = self.env['hr.employee'].create({'name': 'Roll A'})
        self.tech_b = self.env['hr.employee'].create({'name': 'Roll B'})
        self.line_a, self.line_b = self.env['account.analytic.line'].create([{
            'task_id': self.task.id, 'project_id': self.project.id,
            'employees_id': self.tech_a.id, 'name': 'a',
        }, {
            'task_id': self.task.id, 'project_id': self.project.id,
            'employees_id': self.tech_b.id, 'name': 'b',
        }])

    def test_field_exists_so_the_report_can_render(self):
        self.assertIn('technician_job_status', self.env['project.task']._fields)
        self.assertNotIn(
            'my_timer_status', self.env['project.task']._fields,
            'the report must not reference a field that was never declared')

    def test_no_lines_is_not_started(self):
        empty = self.env['project.task'].create({
            'name': 'JC-ROLL-0002', 'is_jobcard': True, 'project_id': self.project.id,
        })
        self.assertEqual(empty.technician_job_status, 'not_started')

    def test_any_running_makes_the_job_running(self):
        self.line_a.action_admin_start()
        self.task.invalidate_recordset(['technician_job_status'])
        self.assertEqual(self.task.technician_job_status, 'running')

    def test_all_paused_makes_the_job_paused(self):
        self.line_a.action_admin_start()
        self.line_a.action_admin_pause()
        self.task.invalidate_recordset(['technician_job_status'])
        self.assertEqual(self.task.technician_job_status, 'paused')

    def test_completed_only_when_every_record_is_closed(self):
        self.line_a.action_admin_start()
        self.line_a.action_admin_end()
        self.task.invalidate_recordset(['technician_job_status'])
        self.assertNotEqual(self.task.technician_job_status, 'completed',
                            'one technician still has an open record')
        self.line_b.action_admin_start()
        self.line_b.action_admin_end()
        self.task.invalidate_recordset(['technician_job_status'])
        self.assertEqual(self.task.technician_job_status, 'completed')

    def test_report_renders_without_raising(self):
        self.line_a.action_admin_start()
        report = self.env.ref(
            'odex_garage_technician_portal.action_report_technician_job')
        html = report._render_qweb_html(report.report_name, self.task.ids)[0]
        self.assertIn(b'Job Card Work Report', html)

