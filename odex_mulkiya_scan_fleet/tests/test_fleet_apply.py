# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.odex_mulkiya_scan.services import constants
from odoo.addons.odex_mulkiya_scan.tests.test_ocr import sample_image


@tagged('post_install', '-at_install', 'mulkiya')
class TestFleetApply(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param(constants.PARAM_PROVIDER, 'demo')
        params.set_param(constants.PARAM_ENABLED, 'True')

        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Nissan'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'NV350', 'brand_id': cls.brand.id})
        cls.other_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Placeholder', 'brand_id': cls.brand.id})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.other_model.id,
            'license_plate': 'TMP-0001',
        })
        cls.Scan = cls.env['odex.mulkiya.scan']

    def _scanned(self, vehicle=None):
        scan = self.Scan.create({
            'front_image': sample_image(),
            'back_image': sample_image(),
            'vehicle_id': (vehicle or self.vehicle).id,
        })
        scan.action_scan()
        return scan

    # ------------------------------------------------------------------
    def test_button_opens_dialog(self):
        action = self.vehicle.action_scan_mulkiya()
        self.assertEqual(action['res_model'], 'odex.mulkiya.scan')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_vehicle_id'], self.vehicle.id)

    def test_mapping_defaults_are_installed(self):
        mappings = self.env['odex.mulkiya.fleet.mapping'].search([])
        keys = set(mappings.mapped('field_key'))
        self.assertEqual(keys, set(constants.MULKIYA_FIELDS))

    def test_unknown_target_field_is_skipped(self):
        self.env['odex.mulkiya.fleet.mapping'].search([
            ('field_key', '=', 'engine_no')]).write({'field_name': 'no_such_field'})
        active = self.env['odex.mulkiya.fleet.mapping'].get_active_mappings()
        self.assertNotIn('engine_no', active.mapped('field_key'))

    def test_matching_finds_brand_and_model(self):
        scan = self._scanned()
        self.assertEqual(scan.get_matched_record('make'), self.brand)
        self.assertEqual(scan.get_matched_record('model'), self.model)

    def test_apply_writes_vehicle(self):
        scan = self._scanned()
        self.assertTrue(scan.apply_preview)
        scan.action_apply_to_vehicle()

        self.assertEqual(self.vehicle.vin_sn, 'JN6BE6DSXF9008830')
        self.assertEqual(self.vehicle.license_plate, '8830')
        self.assertEqual(self.vehicle.model_id, self.model)
        self.assertEqual(scan.state, constants.STATE_APPLIED)
        self.assertEqual(scan.applied_uid, self.env.user)
        self.assertEqual(scan.applied_reference,
                         'fleet.vehicle,%s' % self.vehicle.id)

    def test_apply_attaches_documents(self):
        scan = self._scanned()
        scan.action_apply_to_vehicle()
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'fleet.vehicle'),
            ('res_id', '=', self.vehicle.id),
            ('res_field', '=', False),
        ])
        self.assertEqual(len(attachments), 2)
        self.assertTrue(any('Front' in a.name for a in attachments))
        self.assertTrue(any('Back' in a.name for a in attachments))

    def test_apply_requires_scanned_data(self):
        scan = self.Scan.create({'vehicle_id': self.vehicle.id})
        with self.assertRaises(UserError):
            scan.action_apply_to_vehicle()

    def test_overwrite_flag_is_respected(self):
        self.vehicle.write({'license_plate': 'KEEP-ME'})
        self.env['odex.mulkiya.fleet.mapping'].search([
            ('field_key', '=', 'license_plate')]).write({'overwrite': False})
        scan = self._scanned()
        scan.action_apply_to_vehicle()
        self.assertEqual(self.vehicle.license_plate, 'KEEP-ME')
        self.assertEqual(self.vehicle.vin_sn, 'JN6BE6DSXF9008830')

    def test_missing_master_record_is_reported_not_created(self):
        before = self.env['fleet.vehicle.model.brand'].search_count([])
        scan = self._scanned()
        scan.write({'make': 'Brand Which Does Not Exist'})
        values, skipped = scan._prepare_vehicle_values(self.vehicle)
        self.assertTrue(any('Make' in message for message in skipped))
        self.assertEqual(
            self.env['fleet.vehicle.model.brand'].search_count([]), before)

    def test_duplicate_vin_against_vehicles(self):
        other = self.env['fleet.vehicle'].create({
            'model_id': self.other_model.id,
            'license_plate': 'DUP-0001',
            'vin_sn': 'JN6BE6DSXF9008830',
        })
        scan = self._scanned()
        self.assertTrue(scan.duplicate_warning)
        self.assertIn(other.display_name, scan.duplicate_warning)
        # The warning never blocks the workflow.
        scan.action_apply_to_vehicle()
        self.assertEqual(scan.state, constants.STATE_APPLIED)

    def test_no_duplicate_warning_for_the_target_vehicle(self):
        scan = self._scanned()
        scan.action_apply_to_vehicle()
        scan.invalidate_recordset()
        self.assertFalse(scan.duplicate_warning)

    def test_vehicle_scan_count(self):
        self._scanned()
        self.vehicle.invalidate_recordset()
        self.assertEqual(self.vehicle.mulkiya_scan_count, 1)

    def test_standalone_scan_still_refuses_to_apply(self):
        scan = self.Scan.create({
            'front_image': sample_image(),
            'back_image': sample_image(),
        })
        scan.action_scan()
        scan.action_confirm()
        with self.assertRaises(UserError):
            scan.action_apply()


@tagged('post_install', '-at_install', 'mulkiya')
class TestFormScanner(TransactionCase):
    """The in-form scanner must work while the vehicle is being created."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param(constants.PARAM_PROVIDER, 'demo')
        params.set_param(constants.PARAM_ENABLED, 'True')
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Nissan'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'NV350', 'brand_id': cls.brand.id})
        cls.Scan = cls.env['odex.mulkiya.scan']

    def test_scan_from_images_returns_client_payload(self):
        payload = self.Scan.scan_from_images(
            sample_image(), sample_image(), 'fleet.vehicle,new')
        self.assertTrue(payload['success'])
        self.assertTrue(payload['scan_number'].startswith('MUL/'))
        keys = {entry['key'] for entry in payload['fields']}
        self.assertEqual(keys, set(constants.MULKIYA_FIELDS))
        vin = next(f for f in payload['fields'] if f['key'] == 'vin_sn')
        self.assertEqual(vin['value'], 'JN6BE6DSXF9008830')
        self.assertTrue(vin['confidence'])

    def test_scan_failure_returns_error_payload(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(constants.PARAM_PROVIDER, 'anthropic')
        params.set_param(constants.PARAM_API_KEY, '')
        try:
            payload = self.Scan.scan_from_images(sample_image(), sample_image())
            self.assertFalse(payload['success'])
            self.assertTrue(payload['error'])
        finally:
            params.set_param(constants.PARAM_PROVIDER, 'demo')

    def test_user_correction_is_rematched(self):
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        other = self.env['fleet.vehicle.model.brand'].create({'name': 'Toyota'})
        updated = scan.update_values({'make': 'Toyota'})
        make = next(f for f in updated['fields'] if f['key'] == 'make')
        self.assertEqual(make['value'], 'Toyota')
        self.assertEqual(scan.get_matched_record('make'), other)

    def test_apply_to_form_without_vehicle(self):
        """No vehicle exists yet: values come back, nothing is written to Fleet."""
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        before = self.env['fleet.vehicle'].search_count([])
        result = scan.apply_to_form({}, False)

        self.assertTrue(result['success'])
        self.assertEqual(self.env['fleet.vehicle'].search_count([]), before)
        self.assertEqual(scan.state, constants.STATE_VERIFIED)

        values = result['form_values']
        self.assertEqual(values['vin_sn'], 'JN6BE6DSXF9008830')
        self.assertEqual(values['model_id']['id'], self.model.id)
        self.assertEqual(values['model_id']['display_name'],
                         self.model.display_name)

    def test_apply_to_form_with_saved_vehicle_marks_applied(self):
        vehicle = self.env['fleet.vehicle'].create({'model_id': self.model.id})
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        result = scan.apply_to_form({}, vehicle.id)
        self.assertTrue(result['success'])
        self.assertEqual(scan.state, constants.STATE_APPLIED)
        self.assertEqual(scan.vehicle_id, vehicle)

    def test_apply_to_form_reports_missing_data(self):
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        result = scan.apply_to_form({'vin_sn': ''}, False)
        self.assertFalse(result['success'])
        self.assertIn('Chassis', result['error'])

    def test_link_vehicle_after_save(self):
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        scan.apply_to_form({}, False)
        vehicle = self.env['fleet.vehicle'].create({'model_id': self.model.id})
        scan.link_vehicle(vehicle.id)
        self.assertEqual(scan.vehicle_id, vehicle)
        self.assertEqual(scan.state, constants.STATE_APPLIED)

    def test_field_options_are_master_data(self):
        options = self.Scan.get_field_options()
        makes = [o['name'] for o in options.get('make', [])]
        self.assertIn('Nissan', makes)
        models = options.get('model', [])
        nv350 = next(o for o in models if o['name'] == 'NV350')
        self.assertEqual(nv350['parent_id'], self.brand.id)
        self.assertEqual(nv350['parent_key'], 'make')
        self.assertTrue(options.get('model_year'))
        self.assertTrue(options.get('fuel_type'))

    def test_explicit_selection_wins_over_matching(self):
        toyota = self.env['fleet.vehicle.model.brand'].create({'name': 'Toyota'})
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        scan.update_values({'make': 'Toyota'}, selected={'make': toyota.id})
        self.assertEqual(scan.get_matched_record('make'), toyota)

    def test_apply_to_form_uses_selected_records(self):
        toyota = self.env['fleet.vehicle.model.brand'].create({'name': 'Toyota'})
        land = self.env['fleet.vehicle.model'].create({
            'name': 'Land Cruiser', 'brand_id': toyota.id})
        payload = self.Scan.scan_from_images(sample_image(), sample_image())
        scan = self.Scan.browse(payload['scan_id'])
        result = scan.apply_to_form(
            {'make': 'Toyota', 'model': 'Land Cruiser'}, False,
            selected={'make': toyota.id, 'model': land.id})
        self.assertTrue(result['success'])
        self.assertEqual(result['form_values']['model_id']['id'], land.id)
