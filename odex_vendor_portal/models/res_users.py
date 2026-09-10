# -*- coding: utf-8 -*-
from odoo import api, fields, models

VENDOR_GROUP = 'odex_vendor_portal.group_vendor_portal'
PORTAL_GROUP = 'base.group_portal'


class ResUsers(models.Model):
    _inherit = 'res.users'

    portal_user_type = fields.Selection(
        selection=[
            ('customer', 'Customer'),
            ('vendor', 'Vendor'),
        ],
        string='Portal User Type',
        default='customer',
        required=True,
        help="Only applies to portal users.\n"
             "Customer: the user lands on the existing Customer Portal.\n"
             "Vendor: the user lands on the Vendor Portal and only sees "
             "vendor documents (RFQs, purchase orders, bills).",
    )

    # Allow a portal user to read this field on their own record.
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['portal_user_type']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_vendor_portal_user(self):
        """True when this user must be routed to the Vendor Portal.

        The group membership - not the selection field - is the source of
        truth, so that a hand made group assignment also works and so that
        the check never depends on field level read rights.
        """
        self.ensure_one()
        user = self.sudo()
        group = self.env.ref(VENDOR_GROUP, raise_if_not_found=False)
        if not group or user._is_internal() or user._is_public():
            return False
        return group.id in user.groups_id.ids

    def _sync_vendor_portal_group(self):
        """Keep the vendor group in sync with ``portal_user_type``."""
        group = self.env.ref(VENDOR_GROUP, raise_if_not_found=False)
        portal_group = self.env.ref(PORTAL_GROUP, raise_if_not_found=False)
        if not group or not portal_group:
            return
        for user in self.sudo():
            # Never touch internal or public users: the vendor group implies
            # base.group_portal and would break the user type constraint.
            if user._is_internal() or user._is_public():
                continue
            if user.portal_user_type == 'vendor':
                if group.id not in user.groups_id.ids:
                    user.with_context(vendor_portal_sync=True).write({
                        'groups_id': [(4, portal_group.id), (4, group.id)],
                    })
                partner = user.partner_id.commercial_partner_id
                if partner and not partner.supplier_rank:
                    partner.sudo().write({'supplier_rank': 1})
            elif group.id in user.groups_id.ids:
                user.with_context(vendor_portal_sync=True).write({
                    'groups_id': [(3, group.id)],
                })

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not self.env.context.get('vendor_portal_sync'):
            users._sync_vendor_portal_group()
        return users

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('vendor_portal_sync'):
            return res
        if 'portal_user_type' in vals or 'groups_id' in vals:
            self._sync_vendor_portal_group()
        return res
