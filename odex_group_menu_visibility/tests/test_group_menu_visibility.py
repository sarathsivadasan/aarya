# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestGroupMenuVisibility(TransactionCase):
    """Menu tree built for the tests::

        ODEX Test Root                (folder)
        |-- Branch A                  (folder)
        |   |-- Leaf A1               (action)
        |   `-- Leaf A2               (action)
        |-- Branch B                  (folder)
        |   |-- Leaf B1               (action)
        |   `-- Sub B2                (folder)
        |        `-- Leaf B2a         (action)   <- 4 levels deep
        `-- Leaf C                    (action)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Menu = cls.env['ir.ui.menu']

        cls.action = cls.env['ir.actions.act_window'].create({
            'name': 'ODEX Test Partners',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
        })
        action_ref = 'ir.actions.act_window,%d' % cls.action.id

        cls.root = cls.Menu.create({'name': 'ODEX Test Root', 'sequence': 900})
        cls.branch_a = cls.Menu.create({'name': 'Branch A', 'parent_id': cls.root.id})
        cls.leaf_a1 = cls.Menu.create({
            'name': 'Leaf A1', 'parent_id': cls.branch_a.id, 'action': action_ref})
        cls.leaf_a2 = cls.Menu.create({
            'name': 'Leaf A2', 'parent_id': cls.branch_a.id, 'action': action_ref})
        cls.branch_b = cls.Menu.create({'name': 'Branch B', 'parent_id': cls.root.id})
        cls.leaf_b1 = cls.Menu.create({
            'name': 'Leaf B1', 'parent_id': cls.branch_b.id, 'action': action_ref})
        cls.sub_b2 = cls.Menu.create({'name': 'Sub B2', 'parent_id': cls.branch_b.id})
        cls.leaf_b2a = cls.Menu.create({
            'name': 'Leaf B2a', 'parent_id': cls.sub_b2.id, 'action': action_ref})
        cls.leaf_c = cls.Menu.create({
            'name': 'Leaf C', 'parent_id': cls.root.id, 'action': action_ref})

        cls.all_test_menus = (
            cls.root + cls.branch_a + cls.leaf_a1 + cls.leaf_a2 + cls.branch_b
            + cls.leaf_b1 + cls.sub_b2 + cls.leaf_b2a + cls.leaf_c
        )

        cls.group_tech = cls.env['res.groups'].create({'name': 'ODEX Garage Technician'})
        cls.group_billing = cls.env['res.groups'].create({'name': 'ODEX Billing'})

        cls.user = new_test_user(cls.env, login='odex_tech', groups='base.group_user')
        cls.user.write({'groups_id': [(4, cls.group_tech.id)]})

    def setUp(self):
        super().setUp()
        # ormcache entries are keyed on group sets, not on the transaction.
        self.env.registry.clear_cache()
        self.addCleanup(self.env.registry.clear_cache)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _visible(self, user=None):
        self.env.registry.clear_cache()
        user = user or self.user
        return set(self.env['ir.ui.menu'].with_user(user)._visible_menu_ids(False))

    def _assert_hidden(self, menus, user=None):
        visible = self._visible(user)
        for menu in menus:
            self.assertNotIn(menu.id, visible, "%s should be hidden" % menu.name)

    def _assert_visible(self, menus, user=None):
        visible = self._visible(user)
        for menu in menus:
            self.assertIn(menu.id, visible, "%s should be visible" % menu.name)

    # ------------------------------------------------------------------
    # 1. no hidden menu configured
    # ------------------------------------------------------------------
    def test_01_no_hidden_menu(self):
        self.assertFalse(self.env['ir.ui.menu'].with_user(self.user)._odex_hidden_menu_ids())
        self._assert_visible(self.all_test_menus)

    # ------------------------------------------------------------------
    # 2. one group / one hidden menu (child)
    # ------------------------------------------------------------------
    def test_02_single_hidden_child(self):
        self.group_tech.hidden_menu_ids = self.leaf_a1
        self._assert_hidden(self.leaf_a1)
        self._assert_visible(self.root + self.branch_a + self.leaf_a2 + self.leaf_c)

    # ------------------------------------------------------------------
    # 3. one group / several hidden menus
    # ------------------------------------------------------------------
    def test_03_multiple_hidden_menus(self):
        self.group_tech.hidden_menu_ids = self.leaf_a1 + self.leaf_b1
        self._assert_hidden(self.leaf_a1 + self.leaf_b1)
        self._assert_visible(self.leaf_a2 + self.leaf_b2a + self.leaf_c)

    # ------------------------------------------------------------------
    # 4. cumulative behaviour across groups
    # ------------------------------------------------------------------
    def test_04_multiple_groups_are_cumulative(self):
        self.group_tech.hidden_menu_ids = self.branch_a
        self.group_billing.hidden_menu_ids = self.leaf_b1
        self.user.write({'groups_id': [(4, self.group_billing.id)]})
        self._assert_hidden(self.branch_a + self.leaf_a1 + self.leaf_a2 + self.leaf_b1)
        self._assert_visible(self.root + self.branch_b + self.sub_b2 + self.leaf_b2a + self.leaf_c)

    # ------------------------------------------------------------------
    # 5. hiding a parent hides the whole branch
    # ------------------------------------------------------------------
    def test_05_parent_menu_hides_branch(self):
        self.group_tech.hidden_menu_ids = self.branch_b
        self._assert_hidden(self.branch_b + self.leaf_b1 + self.sub_b2 + self.leaf_b2a)
        self._assert_visible(self.root + self.branch_a + self.leaf_a1 + self.leaf_c)

    def test_05b_root_menu_hides_everything(self):
        self.group_tech.hidden_menu_ids = self.root
        self._assert_hidden(self.all_test_menus)
        # unrelated menus are untouched
        self.assertTrue(self._visible())

    # ------------------------------------------------------------------
    # 6/7. children hidden
    # ------------------------------------------------------------------
    def test_06_sibling_stays_visible(self):
        self.group_tech.hidden_menu_ids = self.leaf_a2
        self._assert_hidden(self.leaf_a2)
        self._assert_visible(self.branch_a + self.leaf_a1)

    def test_07_empty_folder_is_pruned(self):
        """All action children hidden -> the empty folder disappears too."""
        self.group_tech.hidden_menu_ids = self.leaf_a1 + self.leaf_a2
        self._assert_hidden(self.leaf_a1 + self.leaf_a2 + self.branch_a)
        self._assert_visible(self.root + self.branch_b + self.leaf_c)

    # ------------------------------------------------------------------
    # 8. user removed from the group
    # ------------------------------------------------------------------
    def test_08_user_removed_from_group(self):
        self.group_tech.hidden_menu_ids = self.branch_a
        self._assert_hidden(self.branch_a)
        self.user.write({'groups_id': [(3, self.group_tech.id)]})
        self._assert_visible(self.branch_a + self.leaf_a1 + self.leaf_a2)

    # ------------------------------------------------------------------
    # 9/10. configuration changed -> caches invalidated
    # ------------------------------------------------------------------
    def test_09_configuration_change_is_applied(self):
        menu_model = self.env['ir.ui.menu'].with_user(self.user)
        self.group_tech.hidden_menu_ids = self.branch_a
        self.assertIn(self.leaf_a1.id, menu_model._odex_hidden_menu_ids())

        self.group_tech.hidden_menu_ids = self.branch_b
        hidden = menu_model._odex_hidden_menu_ids()
        self.assertNotIn(self.leaf_a1.id, hidden)
        self.assertIn(self.leaf_b2a.id, hidden)

        self.group_tech.hidden_menu_ids = [(5, 0, 0)]
        self.assertFalse(menu_model._odex_hidden_menu_ids())

    def test_10_load_menus_payload(self):
        """What the web client downloads must not reference hidden menus."""
        self.group_tech.hidden_menu_ids = self.branch_a
        self.env.registry.clear_cache()
        menus = self.env['ir.ui.menu'].with_user(self.user).load_menus(False)

        for menu in (self.branch_a, self.leaf_a1, self.leaf_a2):
            self.assertNotIn(menu.id, menus)
        for data in menus.values():
            for child in data.get('children') or []:
                self.assertIn(child, menus)
                self.assertNotIn(child, (self.branch_a.id, self.leaf_a1.id, self.leaf_a2.id))
        self.assertIn(self.leaf_c.id, menus)

    # ------------------------------------------------------------------
    # 11. multi company
    # ------------------------------------------------------------------
    def test_11_multi_company(self):
        company_2 = self.env['res.company'].create({'name': 'ODEX Second Company'})
        self.user.write({'company_ids': [(4, company_2.id)]})
        self.group_tech.hidden_menu_ids = self.branch_a

        for company in (self.env.company, company_2):
            self.env.registry.clear_cache()
            menu_model = self.env['ir.ui.menu'].with_user(self.user).with_company(company)
            visible = set(menu_model._visible_menu_ids(False))
            self.assertNotIn(self.branch_a.id, visible)
            self.assertIn(self.leaf_c.id, visible)

    # ------------------------------------------------------------------
    # 12/13. administrator + standard Odoo menus
    # ------------------------------------------------------------------
    def test_12_administrator_is_not_exempt(self):
        admin = new_test_user(
            self.env, login='odex_admin', groups='base.group_user,base.group_system')
        admin.write({'groups_id': [(4, self.group_tech.id)]})
        settings_menu = self.env.ref('base.menu_administration')
        self.group_tech.hidden_menu_ids = settings_menu + self.branch_a

        visible = self._visible(admin)
        self.assertNotIn(settings_menu.id, visible)
        self.assertNotIn(self.branch_a.id, visible)
        self.assertIn(self.leaf_c.id, visible)

    def test_13_access_rights_are_untouched(self):
        self.group_tech.hidden_menu_ids = self.branch_a
        self.env.registry.clear_cache()
        # the model behind the hidden menu is still perfectly readable
        self.assertTrue(
            self.env['ir.model.access'].with_user(self.user).check('res.partner', 'read'))
        self.assertTrue(self.env['res.partner'].with_user(self.user).search([], limit=1))
        # and the action itself is still reachable
        self.assertTrue(self.action.with_user(self.user).read(['name']))

    # ------------------------------------------------------------------
    # 14/15. path search + nested menus
    # ------------------------------------------------------------------
    def test_14_full_path_and_search(self):
        self.assertEqual(
            self.leaf_b2a.odex_full_path,
            'ODEX Test Root / Branch B / Sub B2 / Leaf B2a')
        found = self.env['ir.ui.menu'].with_context(**{'ir.ui.menu.full_list': True}).name_search(
            'Sub B2 / Leaf B2a')
        self.assertIn(self.leaf_b2a.id, [record[0] for record in found])

    def test_15_nested_branch_hidden(self):
        self.group_tech.hidden_menu_ids = self.sub_b2
        self._assert_hidden(self.sub_b2 + self.leaf_b2a)
        self._assert_visible(self.branch_b + self.leaf_b1)

    # ------------------------------------------------------------------
    # 16. large configuration
    # ------------------------------------------------------------------
    def test_16_large_menu_set(self):
        action_ref = 'ir.actions.act_window,%d' % self.action.id
        big_root = self.Menu.create({'name': 'ODEX Big Root', 'sequence': 901})
        children = self.Menu.create([
            {'name': 'Big Child %d' % index, 'parent_id': big_root.id, 'action': action_ref}
            for index in range(150)
        ])
        self.group_tech.hidden_menu_ids = big_root

        hidden = self.env['ir.ui.menu'].with_user(self.user)._odex_hidden_menu_ids()
        self.assertEqual(len(hidden), 151)
        self.assertTrue(set(children.ids) <= set(hidden))
        self._assert_visible(self.all_test_menus)
