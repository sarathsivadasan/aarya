# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestProductPriceVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'ODEX Test Brake Pad',
            'list_price': 250.0,
            'standard_price': 120.0,
        })
        cls.storekeeper = new_test_user(
            cls.env, login='odex_store', groups='base.group_user')
        cls.storekeeper.write({'context_odex_hide_price': True})
        cls.buyer = new_test_user(
            cls.env, login='odex_buyer', groups='base.group_user')

    def setUp(self):
        super().setUp()
        self.env.registry.clear_cache()
        self.addCleanup(self.env.registry.clear_cache)

    # ------------------------------------------------------------------
    def test_01_flag_reaches_the_user_context(self):
        context = self.env['res.users'].with_user(self.storekeeper).context_get()
        self.assertTrue(context.get('odex_hide_price'))
        self.env.registry.clear_cache()
        context = self.env['res.users'].with_user(self.buyer).context_get()
        self.assertFalse(context.get('odex_hide_price'))

    def test_02_values_are_masked_on_read(self):
        values = self.product.with_user(self.storekeeper).read(
            ['name', 'list_price', 'standard_price'])[0]
        self.assertEqual(values['name'], 'ODEX Test Brake Pad')
        self.assertEqual(values['list_price'], 0.0)
        self.assertEqual(values['standard_price'], 0.0)

    def test_03_values_are_intact_for_other_users(self):
        values = self.product.with_user(self.buyer).read(['list_price', 'standard_price'])[0]
        self.assertEqual(values['list_price'], 250.0)
        self.assertEqual(values['standard_price'], 120.0)

    def test_04_template_is_masked_too(self):
        template = self.product.product_tmpl_id.with_user(self.storekeeper)
        values = template.read(['list_price', 'standard_price'])[0]
        self.assertEqual(values['list_price'], 0.0)
        self.assertEqual(values['standard_price'], 0.0)

    def test_05_sudo_is_not_masked(self):
        """Server side logic running as superuser keeps real values."""
        values = self.product.with_user(self.storekeeper).sudo().read(['standard_price'])[0]
        self.assertEqual(values['standard_price'], 120.0)
        # and direct field access is never touched
        self.assertEqual(self.product.with_user(self.storekeeper).standard_price, 120.0)

    def test_06_export_is_masked(self):
        export = self.product.with_user(self.storekeeper).export_data(
            ['name', 'standard_price'])
        self.assertEqual(export['datas'][0][1], '')
        export = self.product.with_user(self.buyer).export_data(['name', 'standard_price'])
        self.assertNotEqual(export['datas'][0][1], '')

    # ------------------------------------------------------------------
    def test_07_views_carry_the_modifier(self):
        for view_type in ('list', 'form', 'kanban'):
            arch = self.env['product.template'].with_user(
                self.storekeeper).get_view(view_type=view_type)['arch']
            self.assertIn(
                "context.get('odex_hide_price')", arch,
                "%s view of product.template should hide prices" % view_type)

    def test_08_list_uses_column_invisible(self):
        arch = self.env['product.template'].get_view(view_type='list')['arch']
        self.assertIn("column_invisible", arch)

    def test_09_view_arch_is_user_independent(self):
        """The injected expression must be identical for every user, so that
        view caching stays correct."""
        hidden = self.env['product.template'].with_user(
            self.storekeeper).get_view(view_type='list')['arch']
        shown = self.env['product.template'].with_user(
            self.buyer).get_view(view_type='list')['arch']
        self.assertEqual(hidden, shown)

    def test_10_access_rights_unchanged(self):
        self.assertTrue(
            self.env['ir.model.access'].with_user(self.storekeeper).check(
                'product.template', 'read'))
        self.assertTrue(
            self.env['product.product'].with_user(self.storekeeper).search(
                [('id', '=', self.product.id)]))
