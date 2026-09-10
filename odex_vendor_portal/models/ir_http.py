# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

CUSTOMER_HOME_PATHS = ('/my', '/my/', '/my/home')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        """Route vendor portal users to the Vendor Portal dashboard.

        Done at dispatch level so the redirect does not depend on the
        controller MRO: any other module overriding ``/my/home`` keeps
        working untouched for customer users.
        """
        try:
            path = request.httprequest.path
            if path in CUSTOMER_HOME_PATHS:
                user = request.env.user
                if user and not user._is_public() and user._is_vendor_portal_user():
                    return request.redirect('/my/vendor')
        except Exception:  # never break dispatching on a guard
            pass
        return super()._dispatch(endpoint)
