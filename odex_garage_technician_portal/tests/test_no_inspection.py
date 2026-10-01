# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNoVehicleInspection(TransactionCase):
    """v5.0.0: Vehicle Inspection support was removed from the portal.
    Guards against it creeping back in."""

    def test_module_does_not_depend_on_vehicle_inspection_report(self):
        module = self.env['ir.module.module'].search(
            [('name', '=', 'odex_garage_technician_portal')], limit=1)
        deps = module.dependencies_id.mapped('name')
        self.assertNotIn('vehicle_inspection_report', deps)

    def test_inspection_menu_and_actions_are_gone(self):
        for xmlid in (
            'odex_garage_technician_portal.menu_technician_inspection',
            'odex_garage_technician_portal.menu_technician_native_inspections',
            'odex_garage_technician_portal.action_technician_my_inspections',
            'odex_garage_technician_portal.action_report_vehicle_inspection',
        ):
            self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False), xmlid)

    def test_part_link_setting_is_gone(self):
        self.assertNotIn('technician_part_link_field', self.env['res.company']._fields)
        self.assertNotIn('technician_part_link_field', self.env['res.config.settings']._fields)

    def test_portal_domain_is_job_cards_only(self):
        domain = self.env['account.analytic.line']._task_type_domain()
        self.assertEqual(domain, [('task_id.is_jobcard', '=', True)])
