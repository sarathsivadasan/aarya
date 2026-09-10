# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    vendor_portal_responded = fields.Boolean(
        string='Quotation Received From Portal', readonly=True, copy=False)
    vendor_response_date = fields.Datetime(
        string='Vendor Response Date', readonly=True, copy=False)
    vendor_response_note = fields.Text(
        string='Vendor Response Note', readonly=True, copy=False)

    def vendor_portal_url(self):
        self.ensure_one()
        if self.state in ('draft', 'sent'):
            return '/my/vendor/rfq/%s' % self.id
        return '/my/vendor/order/%s' % self.id

    def vendor_portal_status(self):
        """(css key, label) used by the portal badges."""
        self.ensure_one()
        if self.state == 'cancel':
            return ('cancel', 'Cancelled')
        if self.state in ('draft', 'sent'):
            if self.vendor_portal_responded:
                return ('responded', 'Quotation Submitted')
            return ('pending', 'Awaiting Your Quotation')
        if self.state == 'done':
            return ('done', 'Locked')
        return ('confirmed', 'Confirmed')

    def vendor_portal_payment_status(self):
        """Aggregated payment state of the bills linked to this order."""
        self.ensure_one()
        # The caller has already checked the ownership of ``self``; only an
        # aggregated status is exposed, never the bill content.
        bills = self.sudo().invoice_ids.filtered(lambda m: m.state == 'posted')
        if not bills:
            return ('nobill', 'Not Billed')
        if all(b.payment_state in ('paid', 'reversed') for b in bills):
            return ('paid', 'Paid')
        if any(b.payment_state in ('partial', 'in_payment') for b in bills):
            return ('partial', 'Partially Paid')
        return ('pending', 'Pending')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def vendor_portal_uom_name(self):
        """UoM label, resolved at runtime.

        The field was renamed between Odoo releases, so probe instead of
        hardcoding ``product_uom`` / ``product_uom_id``.
        """
        self.ensure_one()
        for fname in ('product_uom_id', 'product_uom'):
            if fname in self._fields:
                uom = self[fname]
                return uom.name if uom else ''
        return ''
