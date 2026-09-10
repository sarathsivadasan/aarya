# Group Based Menu Visibility (`odex_group_menu_visibility`)

Odoo 18 Community Edition · ODEX

Adds a **Hidden Menus** configuration on security groups. Every menu selected on
a group disappears from the menu tree of all users belonging to that group,
without touching a single access right and without modifying Odoo core.

---

## 1. Installation

```bash
# copy the module into your addons path
cp -r odex_group_menu_visibility /opt/odoo18/wms25ii/custom-addons/

# restart the server (Python models changed) and install
sudo systemctl restart odoo18-wms25ii
```

Then *Apps → Update Apps List → search "Group Based Menu Visibility" → Install*,
or from the shell:

```bash
odoo-bin -c <config> -d <database> -u odex_group_menu_visibility --stop-after-init
```

Dependencies: `base`, `web`. No external Python library, no npm asset.

## 2. Configuration

1. Enable the developer mode (needed to reach the Groups menu).
2. Go to **Settings → Users & Companies → Groups**.
3. Open a group, e.g. `Garage Technician`.
4. Open the **Menu Visibility** tab.
5. Add the menus to hide in **Hidden Menus** — menus are listed and searchable
   by their full path (`Garage Management / Job Cards`).
6. Save. Users of that group see the new tree on their next page load.

Nothing else has to be configured. Users already logged in get the new menu tree
after a browser refresh (see §5.3).

Only users who can already manage groups (`Administration / Settings`) can edit
this configuration — the module relies entirely on the standard ACLs and record
rules of `res.groups` and creates no new permission of its own. This is why
`security/ir.model.access.csv` contains only its header row: the module
introduces no new model.

## 3. Behaviour

| Situation | Result |
| --- | --- |
| User has no group with hidden menus | Standard Odoo behaviour, byte for byte |
| One hidden menu | That menu only is removed |
| User in several groups | Hidden menus of **all** groups are combined (union) |
| Parent menu hidden | Parent and its complete branch are removed |
| Child menu hidden | Only that child is removed, siblings stay |
| All children of a folder hidden | The now empty folder is removed too |
| User leaves/joins a group | Applies immediately (cache key is the group set) |
| Administrator in a configured group | Rule applies — admins are **not** exempt |

> **Warning (self lock-out).** Because administrators are not exempt, hiding
> `Settings` for a group that an administrator belongs to removes their access
> to the configuration screen. The configuration is still reachable through the
> direct URL (`/odoo/settings`) or `/web#action=base.action_res_groups`, and
> from the shell, since only the *menu display* is affected.

## 4. What this module is NOT

It is a **menu visibility layer**, not an access control mechanism:

```
Odoo access rights  +  Group menu visibility  =  the interface the user sees
```

It never writes `ir.model.access`, never creates or alters record rules, never
grants or removes a permission, and never bypasses Odoo security. Consequence:
**a user whose menu is hidden but who has read access to the underlying model
can still reach the records** through a direct URL, a related field, a report or
XML-RPC. If a piece of data must be *protected*, remove the access right — this
module is for decluttering an interface, not for securing it.

## 5. Technical approach

### 5.1 How menus are built in Odoo 18

The web client downloads the whole menu tree once per session from
`/web/webclient/load_menus/<unique>`, which returns
`ir.ui.menu.load_menus(debug)`. That method:

1. calls `get_user_roots()` — a `search()` on root menus;
2. searches every descendant of those roots, excluding the ids returned by the
   `_load_menus_blacklist()` hook;
3. assembles a `{menu_id: {..., 'children': [...]}}` dictionary plus a `root`
   entry, and is ormcached on `(uid, debug, lang)`.

Every `search` / `search_fetch` on `ir.ui.menu` is post-filtered by
`_filter_visible_menus()`, which asks `_visible_menu_ids(debug)` — the single
source of truth for menu visibility. That method is ormcached on
`frozenset(user.groups_id.ids)` and applies core's own rules: drop menus whose
`groups_id` the user does not have, keep action menus whose model is readable,
and keep a folder menu only when one of its descendants is kept.

The `ir.ui.menu.full_list` context key disables that post-filtering; core uses it
internally to fetch the raw menu list, and so does this module (which is also
what prevents any recursion).

### 5.2 Where this module plugs in

Three supported hooks, all server side — no JavaScript, no OWL patch, no
monkey-patch, no CSS `display: none`:

| Override | Role |
| --- | --- |
| `_odex_hidden_menu_ids()` | Resolves the closed set of hidden ids for the current user. ormcached on the user's group set. |
| `_visible_menu_ids(debug)` | `super()` minus the hidden ids, then re-applies core's folder rule so folders that became empty are pruned. Fast-path returns `super()` untouched when nothing is configured. |
| `_load_menus_blacklist()` | Official core hook: hidden ids are excluded from the `load_menus` query. |
| `load_menus(debug)` | Defensive pruning of the payload (removes hidden entries and any dangling child reference). Normally a no-op. |

Because the filtering happens in `_visible_menu_ids`, it applies everywhere
uniformly: initial load, browser refresh, navigation between apps, the app
switcher, the command palette menu search, and any other `search()` on
`ir.ui.menu` performed outside the `full_list` context.

Branch closure uses the `parent_path` column (`ir.ui.menu` is a `_parent_store`
model, so a descendant is simply a record whose `parent_path` starts with the
parent's `parent_path`). One in-memory prefix test replaces a recursive
`child_of` query — no raw SQL anywhere in the module.

### 5.3 Caching and invalidation

* `_odex_hidden_menu_ids` and `_visible_menu_ids` are ormcached on
  `frozenset(user.groups_id.ids)`: all users sharing a group set share one entry,
  and changing a user's groups changes the key by itself.
* `load_menus` keeps its core per-user cache.
* Changing `hidden_menu_ids` keeps the same cache key, so `res.groups`
  `create` / `write` / `unlink` call `env.registry.clear_cache()` when that field
  is involved. Core already clears the registry cache when menus or user groups
  are written.
* Browsers hold the menu payload for a year (`max-age`), but the `<unique>`
  segment of the URL is a hash of the menu content computed in `session_info`.
  When the configuration changes the hash changes, so the next page load fetches
  a fresh payload — no manual cache clearing needed, a refresh is enough.

Cost when the feature is used: one bounded read of `ir.ui.menu`, once per group
set, per registry lifetime. Cost when it is not used: one cached set lookup that
returns empty, and `_visible_menu_ids` returns core's result unchanged.

### 5.4 Menu path search

`ir.ui.menu.odex_full_path` is a recursive computed field
(`Garage Management / Job Cards`) with a `search=` method, and
`_search_display_name` routes any search containing a `/` to it. So the Hidden
Menus widget can be searched by path, and the selected menus are listed with
their full hierarchy — useful when several menus share a name (`Reports`,
`Configuration`, …).

### 5.5 Multi-company

The configuration is purely group based, as required. Nothing company specific is
stored, and the module never interferes with `res.company` / `allowed_company_ids`
logic: menu filtering runs after core's own visibility computation, which already
applies multi-company rules.

## 6. Tests

```bash
odoo-bin -c <config> -d <database> -i odex_group_menu_visibility \
         --test-enable --test-tags /odex_group_menu_visibility --stop-after-init
```

`tests/test_group_menu_visibility.py` covers: no configuration, single hidden
menu, several hidden menus, several groups (cumulative), parent branch hidden,
child hidden with siblings kept, all children hidden (folder pruned), user
removed from group, configuration changed (cache invalidation), `load_menus`
payload integrity, multi-company, administrator not exempt, access rights
unaffected, standard Odoo menus, nested (4 level) menus, path search, and a
150-menu branch for scale.

## 7. Structure

```
odex_group_menu_visibility/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── ir_ui_menu.py        # visibility hooks + menu path
│   └── res_groups.py        # hidden_menu_ids + cache invalidation
├── security/
│   └── ir.model.access.csv  # header only: no new model
├── tests/
│   ├── __init__.py
│   └── test_group_menu_visibility.py
└── views/
    └── res_groups_views.xml # Menu Visibility tab on the group form
```

No `static/src/js` directory: the filtering is done at the menu-data level, so
no frontend code is required. Adding one would only duplicate — and could
desynchronise from — the server side result.
