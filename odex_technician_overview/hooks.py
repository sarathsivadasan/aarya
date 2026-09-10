# -*- coding: utf-8 -*-
"""Post-init: attach our menus under the existing Workshop root menu if it
exists in this database, so the module never hard-depends on a specific
workshop module xml-id."""


def post_init_hook(env):
    Menu = env["ir.ui.menu"].sudo()
    root = Menu.search(
        [("name", "in", ["Workshop", "Workshop Management", "Garage"]),
         ("parent_id", "=", False)],
        limit=1, order="id asc",
    )
    if not root:
        return
    our_root = env.ref(
        "odex_technician_overview.menu_overview_root",
        raise_if_not_found=False,
    )
    if our_root:
        # Move our two menus directly under the existing Workshop root and
        # drop our fallback container.
        children = Menu.search([("parent_id", "=", our_root.id)])
        children.write({"parent_id": root.id})
        our_root.active = False
