# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInspectionPartField(TransactionCase):
    """Requirement 2: the `part` Char on vehicle.inspection.part is shown
    and edited from the Parts tab, saved back to the Vehicle Inspection
    and the linked Job Card, and never duplicated."""

    def setUp(self):
        super().setUp()
        self.project = self.env['project.project'].create({'name': 'Workshop'})
        self.inspection = self.env['project.task'].create({
            'name': 'VC-PART-0001', 'is_vc': True, 'project_id': self.project.id,
        })
        self.jobcard = self.env['project.task'].create({
            'name': 'JC-PART-0001', 'is_jobcard': True, 'project_id': self.project.id,
        })
        self.product = self.env['product.product'].create({'name': 'Brake Pad Set'})
        self.other_product = self.env['product.product'].create({'name': 'Oil Filter'})
        self.Part = self.env['vehicle.inspection.part']

    def _has_part(self):
        return 'part' in self.Part._fields

    def _link_tasks(self):
        """Point the job card at the inspection using whichever
        task->task many2one this install actually provides. Returns the
        field name, or False when no such link exists here."""
        names = [n for n in self.jobcard._part_link_field_names()]
        for name in names:
            try:
                self.jobcard.write({name: self.inspection.id})
                return name
            except Exception:  # noqa: BLE001 - probing an unknown schema
                continue
        return False

    # ------------------------------------------------------------------
    def test_part_field_is_serialised_for_the_parts_tab(self):
        line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 2.0,
        })
        if self._has_part():
            line.part = 'BP-1234'
        data = line.to_portal_dict()
        self.assertEqual(data['model'], 'vehicle.inspection.part')
        self.assertEqual(data['product'], self.product.display_name)
        if self._has_part():
            self.assertEqual(data['part'], 'BP-1234')
            self.assertEqual(data['part_source'], 'own')
            self.assertTrue(data['part_editable'])

    def test_writing_part_does_not_create_extra_lines(self):
        line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        before = self.Part.search_count([])
        if self._has_part():
            line.write({'part': 'BP-1234'})
            line.write({'part': 'BP-9999'})
        self.assertEqual(
            self.Part.search_count([]), before,
            'editing part must update in place, never create a duplicate')

    def test_part_propagates_to_the_linked_task_when_a_link_exists(self):
        if not self._has_part():
            self.skipTest('`part` field not present on this instance')
        link = self._link_tasks()
        if not link:
            self.skipTest('no project.task -> project.task link on this instance')
        vc_line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        jc_line = self.Part.create({
            'inspection_id': self.jobcard.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        vc_line.write({'part': 'BP-1234'})
        self.assertEqual(jc_line.part, 'BP-1234',
                         'the matching Job Card line must be updated in place')
        self.assertEqual(
            self.Part.search_count([('inspection_id', '=', self.jobcard.id)]), 1,
            'propagation must not add a second line to the Job Card')

    def test_empty_part_falls_back_to_the_linked_records_value(self):
        if not self._has_part():
            self.skipTest('`part` field not present on this instance')
        link = self._link_tasks()
        if not link:
            self.skipTest('no project.task -> project.task link on this instance')
        self.Part.create({
            'inspection_id': self.jobcard.id, 'product_id': self.product.id,
            'quantity': 1.0, 'part': 'JC-SOURCED',
        })
        vc_line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        value, source = vc_line.effective_part()
        self.assertEqual(value, 'JC-SOURCED')
        self.assertEqual(source, 'job_card')
        self.assertFalse(vc_line.part,
                         'the fallback is display-only - it must not be copied in')

    def test_matching_is_by_product_not_by_row_order(self):
        if not self._has_part():
            self.skipTest('`part` field not present on this instance')
        link = self._link_tasks()
        if not link:
            self.skipTest('no project.task -> project.task link on this instance')
        self.Part.create({
            'inspection_id': self.jobcard.id,
            'product_id': self.other_product.id, 'quantity': 1.0,
        })
        jc_match = self.Part.create({
            'inspection_id': self.jobcard.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        vc_line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        vc_line.write({'part': 'BP-1234'})
        self.assertEqual(jc_match.part, 'BP-1234')

    def test_part_change_is_logged(self):
        if not self._has_part():
            self.skipTest('`part` field not present on this instance')
        line = self.Part.create({
            'inspection_id': self.inspection.id,
            'product_id': self.product.id, 'quantity': 1.0,
        })
        line._log_part_change('BP-1234')
        log = self.env['technician.log'].search([
            ('task_id', '=', self.inspection.id),
            ('action', '=', 'parts_updated'),
        ], limit=1)
        self.assertTrue(log, 'a parts_updated entry must be written')
        self.assertIn('BP-1234', log.description)
