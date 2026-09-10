# -*- coding: utf-8 -*-
"""Menu visibility filtering for :mod:`odex_group_menu_visibility`.

Everything happens server side, inside the very same hooks Odoo 18 already uses
to decide which menus a user may see:

* ``ir.ui.menu._visible_menu_ids(debug)`` -- single source of truth. It is
  ormcached on ``frozenset(user.groups_id.ids)`` and is used by
  ``_filter_visible_menus()``, which in turn filters every ``search`` /
  ``search_fetch`` performed on ``ir.ui.menu`` outside of the
  ``ir.ui.menu.full_list`` context.
* ``ir.ui.menu._load_menus_blacklist()`` -- the official extension hook used by
  ``load_menus()`` to exclude menu ids from the tree sent to the web client.
* ``ir.ui.menu.load_menus(debug)`` -- defensive pruning of the resulting dict.

No CSS, no JavaScript patch, no core file modification.
"""
import re

from odoo import api, fields, models, tools

# Context flag understood by core ``ir.ui.menu``: when set, searches are *not*
# passed through ``_filter_visible_menus()``. Using it here is what prevents an
# infinite recursion when we need the complete menu list from inside the
# visibility computation (core does exactly the same thing).
FULL_LIST_CONTEXT = {'ir.ui.menu.full_list': True}

NEGATIVE_TERM_OPERATORS = ('!=', 'not like', 'not ilike', 'not in')

PATH_SEPARATOR = ' / '

# Menu trees are shallow; this is only a safety net against a corrupted
# parent/child loop.
MAX_PATH_DEPTH = 12


def _normalize_path(value):
    """Make ``Sales/Orders``, ``Sales / Orders`` and ``Sales/  Orders`` equal."""
    return re.sub(r'\s*/\s*', '/', (value or '').strip())


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    odex_full_path = fields.Char(
        string='Menu Path',
        compute='_compute_odex_full_path',
        search='_search_odex_full_path',
        recursive=True,
        compute_sudo=True,
        help="Full hierarchical path of the menu, e.g. 'Garage Management / Job Cards'.",
    )

    # ------------------------------------------------------------------
    # Menu path (display + search helper, requirement §9)
    # ------------------------------------------------------------------
    @api.depends('name', 'parent_id.odex_full_path')
    def _compute_odex_full_path(self):
        for menu in self:
            if menu.parent_id and menu.parent_id.odex_full_path:
                menu.odex_full_path = menu.parent_id.odex_full_path + PATH_SEPARATOR + (menu.name or '')
            else:
                menu.odex_full_path = menu.name or ''

    @api.model
    def _odex_path_matches(self, path, operator, value):
        path = _normalize_path(path)
        term = _normalize_path(value if isinstance(value, str) else '')
        if operator in ('=', '!='):
            result = path == term
        elif operator in ('like', 'not like'):
            result = term in path
        else:  # ilike / not ilike / =ilike / =like and anything unexpected
            result = term.lower() in path.lower()
        return not result if operator in NEGATIVE_TERM_OPERATORS else result

    def _search_odex_full_path(self, operator, value):
        """Allow searching menus by their hierarchical path.

        ``odex_full_path`` is a non stored computed field, so the search is done
        in memory over the (bounded, few hundred records) menu table. The result
        is a plain ``id in [...]`` domain, which keeps it a normal ORM search.
        """
        if not isinstance(value, str):
            return [('name', operator, value)]
        menus = self.sudo().with_context(**FULL_LIST_CONTEXT).search([])
        matched = menus.filtered(
            lambda menu: self._odex_path_matches(menu.odex_full_path, operator, value)
        )
        return [('id', 'in', matched.ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Let the Hidden Menus widget find ``Sales / Orders`` as typed."""
        if isinstance(value, str) and '/' in value:
            return self._search_odex_full_path(operator, value)
        return super()._search_display_name(operator, value)

    # ------------------------------------------------------------------
    # Hidden menu resolution
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)')
    def _odex_hidden_menu_ids(self):
        """Return the closed set of menu ids hidden for the current user.

        "Closed" means: every menu configured on any of the user's groups, plus
        all of its descendants (requirement §5 -- hiding a parent hides the
        whole branch).

        Cached on the user's group set: users sharing the same groups share the
        entry, a change of group membership changes the key by itself, and any
        change of configuration clears the registry cache (see ``res.groups``).
        """
        groups = self.env.user.groups_id
        if not groups:
            return frozenset()

        configured = groups.sudo().mapped('hidden_menu_ids')
        if not configured:
            return frozenset()

        hidden = set(configured.ids)

        # ``ir.ui.menu`` is a _parent_store model: ``parent_path`` holds
        # '1/5/12/', so a single prefix test yields the whole branch without any
        # recursive query and without SQL.
        prefixes = tuple(menu.parent_path for menu in configured if menu.parent_path)
        if prefixes:
            all_menus = self.sudo().with_context(**FULL_LIST_CONTEXT).search([])
            hidden |= {
                menu.id for menu in all_menus
                if menu.parent_path and menu.parent_path.startswith(prefixes)
            }
        else:  # pragma: no cover - defensive, parent_path is always computed
            hidden |= set(self.sudo().with_context(**FULL_LIST_CONTEXT).search(
                [('id', 'child_of', configured.ids)]).ids)

        return frozenset(hidden)

    # ------------------------------------------------------------------
    # Core visibility hooks
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        """Remove hidden branches from the set of menus visible to the user.

        After removing the hidden ids, folder menus (menus without an action)
        that no longer lead to any visible action menu are pruned as well, which
        is exactly the rule core applies when it builds the set: a folder is
        visible only because one of its descendants is.
        """
        visible = super()._visible_menu_ids(debug)
        hidden = self._odex_hidden_menu_ids()
        if not hidden:
            # Nothing configured for this user: strictly standard behaviour.
            return visible

        remaining = set(visible) - hidden
        if not remaining:
            return remaining

        result = set()
        menus = self.sudo().with_context(**FULL_LIST_CONTEXT).browse(sorted(remaining))
        for menu in menus:
            if not menu.action:
                continue
            result.add(menu.id)
            parent = menu.parent_id
            while parent and parent.id in remaining and parent.id not in result:
                result.add(parent.id)
                parent = parent.parent_id
        return result

    @api.model
    def _load_menus_blacklist(self):
        """Official hook used by ``load_menus()`` to exclude menu ids."""
        parent_hook = getattr(super(), '_load_menus_blacklist', None)
        blacklist = list(parent_hook()) if parent_hook else []
        return blacklist + list(self._odex_hidden_menu_ids())

    @api.model
    def load_menus(self, debug):
        """Defensive pruning of the menu tree handed to the web client.

        With ``_visible_menu_ids`` and ``_load_menus_blacklist`` in place this
        is normally a no-op; it guarantees the payload can never contain a
        hidden id (nor a dangling reference to one) even if a third party module
        bypasses the search filtering.
        """
        menus = super().load_menus(debug)
        hidden = self._odex_hidden_menu_ids()
        if not hidden or not any(menu_id in menus for menu_id in hidden):
            return menus

        # Copy before mutating: the dict returned by super() is ormcached.
        pruned = {
            key: dict(value, children=list(value.get('children') or []))
            for key, value in menus.items()
            if key == 'root' or key not in hidden
        }
        for value in pruned.values():
            value['children'] = [child for child in value['children'] if child in pruned]
        return pruned
