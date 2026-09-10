# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def vendor_portal_payment_status(self):
        """(css key, label) shown on the Pending Payments page."""
        self.ensure_one()
        if self.payment_state in ('paid', 'reversed'):
            return ('paid', 'Paid')
        if self.payment_state in ('partial', 'in_payment'):
            return ('partial', 'Partially Paid')
        today = fields.Date.context_today(self)
        if self.invoice_date_due and self.invoice_date_due < today:
            return ('overdue', 'Overdue')
        return ('pending', 'Pending')

    def vendor_portal_paid_amount(self):
        self.ensure_one()
        return (self.amount_total or 0.0) - (self.amount_residual or 0.0)
