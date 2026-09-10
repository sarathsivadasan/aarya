# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..services.normalization_service import NormalizationService


@tagged('post_install', '-at_install', 'mulkiya')
class TestNormalization(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = NormalizationService(cls.env)

    def test_vin_cleanup(self):
        self.assertEqual(
            self.service.normalize_vin('  jn6be6dsxf90-08830 '),
            'JN6BE6DSXF9008830')
        self.assertEqual(
            self.service.normalize_vin('Chassis No. JN6BE6DSXF9008830'),
            'JN6BE6DSXF9008830')

    def test_vin_is_never_auto_corrected(self):
        # O / I / Q must be reported, not silently replaced.
        suspicious = 'JN6BE6DSXFO008830'
        self.assertEqual(self.service.normalize_vin(suspicious), suspicious)
        warnings = self.service.check_vin(suspicious)
        self.assertTrue(warnings)
        self.assertIn('O', warnings[0])

    def test_vin_length_warning(self):
        self.assertTrue(self.service.check_vin('JN6BE6DS'))
        self.assertFalse(self.service.check_vin('JN6BE6DSXF9008830'))

    def test_engine_number(self):
        self.assertEqual(
            self.service.normalize_identifier('yd25  123456t'), 'YD25 123456T')

    def test_arabic_digits(self):
        self.assertEqual(self.service.normalize_plate('\u0668\u0668\u0663\u0660'), '8830')
        self.assertEqual(self.service.normalize_year('\u0662\u0660\u0661\u0664'), '2014')

    def test_plate_cleanup(self):
        self.assertEqual(self.service.normalize_plate(' 08830 '), '8830')
        self.assertEqual(self.service.normalize_plate_code(' 1 '), '1')

    def test_integer(self):
        self.assertEqual(self.service.normalize_integer('4 cylinders'), 4)
        self.assertEqual(self.service.normalize_integer(''), 0)

    def test_make_alias_english(self):
        self.assertEqual(self.service.normalize_name('make', 'NISSAN'), 'Nissan')
        self.assertEqual(self.service.normalize_name('make', 'nissan'), 'Nissan')

    def test_make_alias_arabic(self):
        self.assertEqual(
            self.service.normalize_name('make', '\u0646\u064a\u0633\u0627\u0646'),
            'Nissan')

    def test_emirate_alias_arabic(self):
        self.assertEqual(
            self.service.normalize_name(
                'registration_emirate', '\u0623\u0628\u0648\u0638\u0628\u064a'),
            'Abu Dhabi')

    def test_model_keeps_alphanumeric_case(self):
        self.assertEqual(self.service.normalize_name('model', 'nv350'), 'NV350')

    def test_confidence_scale(self):
        payload = {'make': {'value': 'NISSAN', 'confidence': 0.96}}
        result = self.service.normalize_payload(payload)
        self.assertEqual(result['make']['confidence'], 96)
        self.assertEqual(result['make']['value'], 'Nissan')
        self.assertEqual(result['make']['raw_value'], 'NISSAN')
