# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    hidden_menu_ids = fields.Many2many(
        comodel_name='ir.ui.menu',
        relation='res_groups_hidden_menu_rel',
        column1='gid',
        column2='menu_id',
        string='Hidden Menus',
        help="Menus listed here are removed from the menu tree of every user "
             "belonging to this group. Hiding a parent menu hides its whole "
             "branch. This does not change any access right: it is a display "
             "layer only.",
    )
    hidden_menu_count = fields.Integer(
        string='Hidden Menus Count',
        compute='_compute_hidden_menu_count',
    )

    @api.depends('hidden_menu_ids')
    def _compute_hidden_menu_count(self):
        for group in self:
            group.hidden_menu_count = len(group.hidden_menu_ids)

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------
    # ``ir.ui.menu._odex_hidden_menu_ids`` / ``_visible_menu_ids`` /
    # ``load_menus`` are ormcached. Membership changes already invalidate them
    # (the cache key is the user's group set, and ``res.users.write`` clears the
    # registry cache), but a change of *configuration* keeps the same key, so it
    # has to be flushed explicitly.
    def _odex_clear_menu_cache(self):
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        if any('hidden_menu_ids' in vals for vals in vals_list):
            self._odex_clear_menu_cache()
        return groups

    def write(self, vals):
        result = super().write(vals)
        if 'hidden_menu_ids' in vals:
            self._odex_clear_menu_cache()
        return result

    def unlink(self):
        had_configuration = any(group.hidden_menu_ids for group in self)
        result = super().unlink()
        if had_configuration:
            self._odex_clear_menu_cache()
        return result
