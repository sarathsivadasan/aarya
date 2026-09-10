# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..services.matching_service import MatchingService


@tagged('post_install', '-at_install', 'mulkiya')
class TestMatching(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = MatchingService(cls.env)

    def test_missing_model_is_ignored(self):
        """A rule pointing at an uninstalled model must not raise."""
        self.env['odex.mulkiya.match.rule'].create({
            'field_key': 'color',
            'model_name': 'this.model.does.not.exist',
            'search_field': 'name',
            'sequence': 1,
        })
        service = MatchingService(self.env)
        result = service.match_field('color', 'White')
        self.assertFalse(result['matched'])
        self.assertEqual(result['value'], 'White')

    def test_match_against_generic_model(self):
        """Matching works against any model, Fleet is not required."""
        partner = self.env['res.partner'].create({'name': 'Mulkiya Test Brand'})
        self.env['odex.mulkiya.match.rule'].create({
            'field_key': 'make',
            'model_name': 'res.partner',
            'search_field': 'name',
            'sequence': 1,
        })
        service = MatchingService(self.env)
        result = service.match_field('make', 'mulkiya test brand')
        self.assertTrue(result['matched'])
        self.assertEqual(result['record_id'], partner.id)
        self.assertEqual(result['model'], 'res.partner')

    def test_no_master_record_is_created(self):
        before = self.env['res.partner'].search_count([])
        self.env['odex.mulkiya.match.rule'].create({
            'field_key': 'make',
            'model_name': 'res.partner',
            'search_field': 'name',
            'sequence': 1,
        })
        MatchingService(self.env).match_field('make', 'Brand That Does Not Exist')
        self.assertEqual(self.env['res.partner'].search_count([]), before)

    def test_unmatched_payload_shape(self):
        result = self.service.match_field('color', 'Pearl White')
        self.assertIn('matched', result)
        self.assertIn('model', result)
        self.assertIn('record_id', result)
        self.assertFalse(result['matched'])
