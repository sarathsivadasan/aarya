# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class VendorHome(Home):
    """Send vendor portal users to the Vendor Portal right after login.

    The standard portal login flow is untouched: only the landing URL of a
    user carrying the Vendor Portal group changes, and only when no explicit
    ``redirect`` was requested.
    """

    def _login_redirect(self, uid, redirect=None):
        if not redirect:
            user = request.env['res.users'].sudo().browse(uid)
            if user.exists() and user._is_vendor_portal_user():
                return '/my/vendor'
        return super()._login_redirect(uid, redirect=redirect)
