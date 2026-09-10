# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    portal_confirmed = fields.Boolean(
        string="Portal Confirmed",
        default=False,
        copy=False,
        help="Indicates whether this quotation line has been approved by the "
             "customer through the portal.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _portal_check_editable(self):
        """Common guardrail: only draft/sent quotations may be edited."""
        self.ensure_one()
        if self.order_id.state not in ('draft', 'sent'):
            raise UserError(
                _("Only draft quotations can be edited from the portal.")
            )
        return True

    # ------------------------------------------------------------------
    # Portal actions
    # ------------------------------------------------------------------
    def portal_update_qty(self, quantity):
        """Update qty from portal interaction.

        Guardrails:
        - Only draft quotation can be edited.
        - Quantity must be >= 0.
        """
        self.ensure_one()
        self._portal_check_editable()

        try:
            qty = float(quantity)
        except Exception:
            raise UserError(_("Invalid quantity value."))

        if qty < 0:
            raise UserError(_("Quantity cannot be negative."))

        self.write({'product_uom_qty': qty})
        return True

    def portal_set_confirmed(self, confirmed):
        """Store the customer approval flag coming from the portal checkbox.

        The line is never deleted, archived or hidden: the flag is purely an
        approval indicator shared between the customer and the salesperson.
        """
        self.ensure_one()
        self._portal_check_editable()

        self.write({'portal_confirmed': bool(confirmed)})
        return self.portal_confirmed


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # Confirmed-only financial summary
    # ------------------------------------------------------------------
    # The portal summary must reflect only the lines the customer approved.
    # Standard tax computation is NOT modified: the very same account.tax
    # pipeline core uses in _compute_tax_totals is called, just fed with the
    # confirmed subset of _get_priced_lines(). Stored amount_* fields and the
    # native tax_totals field are left untouched, so the backend, the PDF and
    # invoicing keep seeing the full order.

    def tus_get_lines_to_report(self, report_type=None):
        """Lines to render in the quotation document.

        The portal page shows every line (each with its Confirm button), while
        the printed quotation shows only what the customer approved, so the
        PDF matches the summary. Sections and notes are always kept, and once
        the order is no longer editable the full order is printed again.
        """
        self.ensure_one()
        lines = self._get_order_lines_to_report()
        if report_type == 'html' or self.state not in ('draft', 'sent'):
            return lines
        return lines.filtered(
            lambda line: line.display_type or line.portal_confirmed
        )

    def tus_get_confirmed_tax_totals(self):
        """Return a tax_totals summary built from confirmed lines only.

        Falls back to the native totals once the quotation is no longer
        editable (signed / confirmed / cancelled), where the whole order is
        what the customer committed to.
        """
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            return self.tax_totals

        AccountTax = self.env['account.tax']
        lines = self._get_priced_lines().filtered('portal_confirmed')
        base_lines = [
            line._prepare_base_line_for_taxes_computation() for line in lines
        ]
        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return AccountTax._get_tax_totals_summary(
            base_lines=base_lines,
            currency=self.currency_id or self.company_id.currency_id,
            company=self.company_id,
        )

    # ------------------------------------------------------------------
    # Estimated hours (read-through to the linked Vehicle Inspection)
    # ------------------------------------------------------------------
    # No model is created and nothing is stored on the order: the inspection
    # is resolved on the fly and its own records are rendered directly, so the
    # portal always shows the latest data.
    #
    # The link is discovered by introspection rather than hard-coded, so this
    # works whichever Many2one carries the inspection (inspection_id or any
    # other name) and stays inert when the inspection module is not installed.

    def tus_get_inspection(self):
        """Return the Vehicle Inspection linked to this order, or an empty
        recordset when there is none."""
        self.ensure_one()
        for fname, field in self._fields.items():
            if field.type != 'many2one':
                continue
            comodel_name = field.comodel_name
            if comodel_name not in self.env:
                continue
            if 'inspection_estimated_hour_ids' not in self.env[comodel_name]._fields:
                continue
            inspection = self[fname]
            if inspection:
                return inspection
        return self.env['sale.order'].browse()

    def tus_get_estimated_hours(self):
        """Return the vehicle.inspection.estimated.hours records of the linked
        inspection. Empty when no inspection is linked."""
        self.ensure_one()
        inspection = self.tus_get_inspection()
        if not inspection:
            return inspection
        return inspection.inspection_estimated_hour_ids

    def tus_get_total_estimated_hours(self):
        """Sum of assign_hours over the linked inspection's estimated hours."""
        self.ensure_one()
        lines = self.tus_get_estimated_hours()
        if not lines:
            return 0.0
        return sum(lines.mapped('assign_hours'))
