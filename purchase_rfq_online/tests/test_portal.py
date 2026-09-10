# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.base.tests.common import HttpCaseWithUserPortal


@tagged("post_install", "-at_install")
class TestSignature(HttpCaseWithUserPortal):
    def test_01_portal_purchase_signature_tour(self):
        """The goal of this test is to make sure the portal user can sign PO."""

        portal_user_partner = self.partner_portal
        # create a SO to be signed
        purchase_order = self.env["purchase.order"].create(
            {
                "name": "test PO",
                "partner_id": portal_user_partner.id,
                "state": "sent",
            }
        )
        self.env["purchase.order.line"].create(
            {
                "order_id": purchase_order.id,
                "product_id": self.env["product.product"]
                .create({"name": "A product"})
                .id,
            }
        )

        # must be sent to the user so he can see it
        email_act = purchase_order.action_rfq_send()
        email_ctx = email_act.get("context", {})
        purchase_order.with_context(**email_ctx).message_post_with_source(
            self.env["mail.template"].browse(email_ctx.get("default_template_id")),
            subtype_xmlid="mail.mt_comment",
        )

        self.start_tour("/", "purchase_signature", login="portal")
