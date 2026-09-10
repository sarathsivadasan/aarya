# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..services import constants
from .test_ocr import sample_image


@tagged('post_install', '-at_install', 'mulkiya')
class TestScanFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param(constants.PARAM_PROVIDER, 'demo')
        params.set_param(constants.PARAM_ENABLED, 'True')
        params.set_param(constants.PARAM_THRESHOLD, '90')
        cls.Scan = cls.env['odex.mulkiya.scan']

    def _new_scan(self, with_images=True):
        values = {}
        if with_images:
            values.update({
                'front_image': sample_image(),
                'back_image': sample_image(),
            })
        return self.Scan.create(values)

    def test_sequence_and_initial_state(self):
        scan = self._new_scan(with_images=False)
        self.assertTrue(scan.name.startswith('MUL/'))
        self.assertEqual(scan.state, constants.STATE_DRAFT)

    def test_state_moves_to_uploaded(self):
        scan = self._new_scan()
        self.assertEqual(scan.state, constants.STATE_UPLOADED)
        scan.write({'back_image': False})
        self.assertEqual(scan.state, constants.STATE_DRAFT)

    def test_cannot_scan_without_both_images(self):
        scan = self._new_scan(with_images=False)
        scan.write({'front_image': sample_image()})
        with self.assertRaises(UserError):
            scan.action_scan()

    def test_full_workflow(self):
        scan = self._new_scan()
        scan.action_scan()
        self.assertEqual(scan.state, constants.STATE_EXTRACTED)
        self.assertEqual(scan.ocr_status, 'done')
        self.assertEqual(scan.vin_sn, 'JN6BE6DSXF9008830')
        self.assertEqual(scan.make, 'Nissan')
        self.assertEqual(scan.vehicle_model, 'NV350')
        self.assertEqual(scan.cylinder_count, 4)
        self.assertEqual(scan.registration_emirate, 'Abu Dhabi')
        self.assertTrue(scan.ocr_confidence)
        self.assertTrue(scan.vin_sn_conf)

        scan.action_confirm()
        self.assertEqual(scan.state, constants.STATE_VERIFIED)
        self.assertEqual(scan.verified_uid, self.env.user)
        self.assertTrue(scan.verified_date)

    def test_values_are_editable_before_confirmation(self):
        scan = self._new_scan()
        scan.action_scan()
        scan.write({'color': 'Pearl White'})
        self.assertEqual(scan.color, 'Pearl White')
        scan.action_confirm()
        self.assertEqual(scan.get_vehicle_data()['color'], 'Pearl White')

    def test_confirm_requires_vin_and_plate(self):
        scan = self._new_scan()
        scan.action_scan()
        scan.write({'vin_sn': False})
        with self.assertRaises(UserError):
            scan.action_confirm()

    def test_get_vehicle_data_contract(self):
        scan = self._new_scan()
        scan.action_scan()
        data = scan.get_vehicle_data()
        self.assertEqual(sorted(data.keys()), sorted(constants.MULKIYA_FIELDS))
        self.assertEqual(data['model'], 'NV350')
        self.assertIsInstance(data['cylinder_count'], int)

    def test_structured_result_contract(self):
        scan = self._new_scan()
        scan.action_scan()
        result = scan.get_structured_result()
        for key in ('success', 'scan_id', 'scan_number', 'status', 'vehicle',
                    'fields', 'warnings'):
            self.assertIn(key, result)
        entry = result['fields']['make']
        for key in ('value', 'confidence', 'matched', 'model', 'record_id'):
            self.assertIn(key, entry)

    def test_duplicate_vin_is_detected_not_blocked(self):
        first = self._new_scan()
        first.action_scan()
        first.action_confirm()
        second = self._new_scan()
        second.action_scan()
        self.assertTrue(second.duplicate_warning)
        # A duplicate never blocks the workflow, it only warns.
        second.action_confirm()
        self.assertEqual(second.state, constants.STATE_VERIFIED)

    def test_rescan_clears_previous_result(self):
        scan = self._new_scan()
        scan.action_scan()
        scan.write({'make': 'Wrong Value'})
        scan.action_rescan()
        self.assertEqual(scan.make, 'Nissan')
        self.assertEqual(scan.state, constants.STATE_EXTRACTED)

    def test_failure_is_recorded(self):
        self.env['ir.config_parameter'].sudo().set_param(
            constants.PARAM_PROVIDER, 'anthropic')
        self.env['ir.config_parameter'].sudo().set_param(
            constants.PARAM_API_KEY, '')
        try:
            scan = self._new_scan()
            scan.action_scan()
            self.assertEqual(scan.state, constants.STATE_FAILED)
            self.assertEqual(scan.ocr_status, 'error')
            self.assertTrue(scan.ocr_error)
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                constants.PARAM_PROVIDER, 'demo')

    def test_attachments_are_stored(self):
        scan = self._new_scan()
        attachments = scan.get_document_attachments()
        self.assertEqual(len(attachments), 2)

    def test_copy_documents_to_record(self):
        scan = self._new_scan()
        partner = self.env['res.partner'].create({'name': 'Mulkiya Target'})
        created = scan.copy_documents_to(partner, prefix='Mulkiya')
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].res_model, 'res.partner')

    def test_mark_applied_audit(self):
        scan = self._new_scan()
        scan.action_scan()
        scan.action_confirm()
        scan.mark_applied('res.partner,1')
        self.assertEqual(scan.state, constants.STATE_APPLIED)
        self.assertEqual(scan.applied_uid, self.env.user)
        self.assertEqual(scan.applied_reference, 'res.partner,1')

    def test_dashboard_data(self):
        self._new_scan()
        data = self.Scan.get_dashboard_data()
        self.assertIn('counts', data)
        self.assertIn('recent', data)
        self.assertGreaterEqual(data['counts']['total'], 1)
