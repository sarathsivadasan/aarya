from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    type_name = fields.Char(compute="_compute_type_name")
    signature = fields.Image(
        copy=False,
        attachment=True,
        max_width=1024,
        max_height=1024,
        help="Signature received through the portal.",
    )
    signed_by = fields.Char(copy=False, help="Name of the person that signed the SO.")
    signed_on = fields.Datetime(help="Date of the signature.", copy=False)

    def preview_purchase_order(self):
        """
        Preview the request for quotation directly on a web interface
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": self.get_portal_url(),
        }

    def _get_portal_return_action(self):
        """
        Return the action used to display orders when
        returning from supplier portal.
        """
        self.ensure_one()
        return self.env.ref("purchase.purchase_rfq")

    @api.depends("state")
    def _compute_type_name(self):
        for record in self:
            record.type_name = (
                self.env._("Quotation")
                if record.state in ("draft", "sent", "cancel")
                else self.env._("Purchase Order")
            )

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"{self.type_name} {self.name}"

    def _has_to_be_signed(self):
        self.ensure_one()
        return self.state in ("draft", "sent") and not self.signed_on
