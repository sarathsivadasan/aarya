# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal


class SalePortalQty(CustomerPortal):

    def _portal_get_order_line(self, order_id, line_id, access_token=None):
        """Resolve and secure an order line reached from the portal.

        Returns a tuple ``(line, error_dict)``. Exactly one of the two is set.
        """
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            # generic error for portal
            return None, {'success': False, 'error': _("Access denied.")}

        line = request.env['sale.order.line'].sudo().browse(int(line_id))
        if not line.exists() or line.order_id.id != order_sudo.id:
            return None, {'success': False, 'error': _("Invalid order line.")}

        return line, None

    def _portal_render_totals(self, order_sudo):
        """Re-render the confirmed-lines totals table so the JS can refresh the
        summary without a page reload."""
        return request.env['ir.qweb']._render(
            'portal_quotation_customize.confirmed_totals_table',
            {
                'sale_order': order_sudo,
                'report_type': 'html',
            },
        )

    @http.route(
        ['/my/orders/<int:order_id>/update_line_qty'],
        type='json',
        auth='public',
        website=True,
    )
    def portal_update_line_qty(self, order_id, line_id, quantity,
                               access_token=None, confirmed=None, **kwargs):
        """Update SO line quantity from portal.

        Security:
        - Access checked via _document_check_access with access_token.
        - Ensures line belongs to that order.

        ``confirmed`` is optional: when provided, the customer approval flag is
        persisted within the very same save action.
        """
        line, error = self._portal_get_order_line(
            order_id, line_id, access_token=access_token
        )
        if error:
            return error

        try:
            line.portal_update_qty(quantity)
            if confirmed is not None:
                line.portal_set_confirmed(confirmed)
        except UserError as e:
            return {'success': False, 'error': str(e)}

        # After successful update, send back portal URL so JS can refresh
        return {
            'success': True,
            'redirect_url': line.order_id.get_portal_url(),
        }

    @http.route(
        ['/my/orders/<int:order_id>/toggle_line_confirmed'],
        type='json',
        auth='public',
        website=True,
    )
    def portal_toggle_line_confirmed(self, order_id, line_id, confirmed,
                                     access_token=None, **kwargs):
        """Persist the customer approval checkbox for a single SO line.

        The line itself is never deleted or modified otherwise.
        """
        line, error = self._portal_get_order_line(
            order_id, line_id, access_token=access_token
        )
        if error:
            return error

        try:
            state = line.portal_set_confirmed(confirmed)
        except UserError as e:
            return {'success': False, 'error': str(e)}

        return {
            'success': True,
            'confirmed': state,
            'totals_html': self._portal_render_totals(line.order_id),
        }
