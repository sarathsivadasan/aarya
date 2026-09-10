# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # The ``context_`` prefix is deliberate: core ``res.users.context_get()``
    # publishes every ``context_*`` field of the user into the session context,
    # so this flag is available to the web client as ``context.get('odex_hide_price')``
    # and can be used directly inside view modifiers. The same prefix also makes
    # the field self-readable (``res.users.read`` allows any ``context_*`` key),
    # while writing it still requires the standard user-administration rights.
    context_odex_hide_price = fields.Boolean(
        string='Hide Cost & Sales Price',
        default=False,
        help="When enabled, this user no longer sees the cost and the sales "
             "price of products (Inventory, Purchase, Sales product views). "
             "This is a visibility setting, not an access right: see README for "
             "its exact scope.",
    )

    def write(self, vals):
        result = super().write(vals)
        if 'context_odex_hide_price' in vals:
            # ``res.users.context_get()`` is ormcached per user.
            self.env.registry.clear_cache()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if any('context_odex_hide_price' in vals for vals in vals_list):
            self.env.registry.clear_cache()
        return users
