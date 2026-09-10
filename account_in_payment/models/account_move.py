# Copyright 2024 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools import config


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _get_invoice_in_payment_state(self):
        """
        We override this method to change the state of the invoice to in_payment
        when the payment is created from the invoice.
        """
        if config["test_enable"] and not self._context.get(
            "test_get_invoice_in_payment_state"
        ):
            return super()._get_invoice_in_payment_state()
        # Check if a payment is linked and what journal type it uses
        payments = self._get_reconciled_payments()
        for payment in payments:
            if payment.journal_id.type == "cash":
                return "paid"
            elif payment.journal_id.type == "bank":
                return "in_payment"

        # Fallback to default
        return super()._get_invoice_in_payment_state()
