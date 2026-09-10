# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTechnicianWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()
        self.user = self.env['res.users'].create({
            'name': 'Workflow Technician', 'login': 'tech_wf_test',
            'email': 'tech_wf_test@example.com',
        })
        self.employee = self.env['hr.employee'].create({
            'name': 'Workflow Technician', 'user_id': self.user.id,
            'workshop_position_type': 'worker',
        })
        self.task = self.env['project.task'].create({
            'name': 'VC-WF-0001', 'is_vc': True, 'user_ids': [(4, self.user.id)],
        })

    def test_start_creates_log_entry(self):
        project = self.env['project.project'].create({'name': 'WF Workshop'})
        self.task.project_id = project.id
        line = self.env['account.analytic.line'].create({
            'task_id': self.task.id, 'project_id': project.id,
            'employees_id': self.employee.id, 'name': 'wf',
        }).with_user(self.user)
        line.action_technician_start()
        logs = self.env['technician.log'].search([('task_id', '=', self.task.id)])
        self.assertTrue(any(l.action == 'started' for l in logs))

    def test_photo_upload_creates_log_entry(self):
        self.task.set_photo_slot(
            1, image='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            desc='Front bumper')
        logs = self.env['technician.log'].search([
            ('task_id', '=', self.task.id), ('action', '=', 'photo_uploaded'),
        ])
        self.assertEqual(len(logs), 1)
        self.assertTrue(self.task.image1)
        self.assertEqual(self.task.image1_desc, 'Front bumper')

    def test_photo_slots_reflect_immediately_on_the_same_task_record(self):
        # this IS the Vehicle Inspection / Job Card record - no separate
        # storage, so the write is visible via a fresh browse immediately
        self.task.set_photo_slot(2, image='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        same_task = self.env['project.task'].browse(self.task.id)
        self.assertTrue(same_task.image2)
        slots = same_task.get_photo_slots()
        slot_2 = next(s for s in slots if s['slot'] == 2)
        self.assertTrue(slot_2['has_image'])

    def test_note_creates_log_entry(self):
        self.env['technician.note'].create({
            'task_id': self.task.id,
            'content': '<p>Customer requested extra check on brakes.</p>',
        })
        logs = self.env['technician.log'].search([
            ('task_id', '=', self.task.id), ('action', '=', 'notes_added'),
        ])
        self.assertEqual(len(logs), 1)

    def test_qc_check_mark_flags_task_passed(self):
        checklist_item = self.env['quality.checklist'].create({
            'name': 'Brake fluid level', 'job_card_id': self.task.id, 'check_mark': False,
        })
        self.task.invalidate_recordset(['qc_passed'])
        self.assertFalse(self.task.qc_passed)

        checklist_item.write({'check_mark': True})
        self.task.invalidate_recordset(['qc_passed'])
        self.assertTrue(self.task.qc_passed)

    def test_qc_section_rows_excluded_from_gate(self):
        # a section/note display row should not block the QC gate even
        # though it has no meaningful check_mark value
        self.env['quality.checklist'].create({
            'name': 'ENGINE COMPARTMENT', 'job_card_id': self.task.id,
            'display_type': 'line_section', 'check_mark': False,
        })
        real_item = self.env['quality.checklist'].create({
            'name': 'Air Filter', 'job_card_id': self.task.id, 'check_mark': True,
        })
        self.task.invalidate_recordset(['qc_passed'])
        self.assertTrue(self.task.qc_passed)

    def test_dashboard_counters_scoped_to_current_user_employee(self):
        counters = self.env['account.analytic.line'].with_user(
            self.user).get_technician_dashboard_counters()
        self.assertIn('assigned', counters)
        self.assertIn('hours_today', counters)

    def test_complaint_line_created_elsewhere_is_visible_via_requested_services_ids(self):
        # simulates a complaint added directly on the Vehicle Inspection
        # form (or Job Card) - the portal must see the exact same record
        # via requested_services_ids, with no separate storage of its own
        service = self.env['job.requested.service'].create({
            'task_id': self.task.id, 'remark': 'Check AC cooling',
        })
        self.assertIn(service, self.task.requested_services_ids)
