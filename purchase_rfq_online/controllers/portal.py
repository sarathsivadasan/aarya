# Part of Odoo. See LICENSE file for full copyright and licensing details.

import binascii
import logging
from functools import partial

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools import formatLang

from odoo.addons.purchase.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

# Defensive upper bound for the free text the vendor may submit from the
# portal, so a public route cannot be used to store arbitrarily large values.
VENDOR_PART_NO_MAX_LENGTH = 128


class PartnerPortal(CustomerPortal):
    @http.route(
        ["/my/purchase/<int:order_id>/update_line"],
        type="json",
        auth="public",
        website=True,
    )
    def po_line_update(
        self,
        line_id,
        remove=False,
        unlink=False,
        order_id=None,
        access_token=None,
        **post,
    ):
        values = self.update_line_dict(
            line_id, remove, unlink, order_id, access_token, **post
        )
        if values:
            return [values["order_line_price_unit"], values["order_amount_total"]]
        return values

    @http.route(
        ["/my/purchase/<int:order_id>/update_line_dict"],
        type="json",
        auth="public",
        website=True,
    )
    def po_line_update_dict(
        self,
        order_id,
        remove=False,
        unlink=False,
        line_id=None,
        access_token=None,
        input_price=False,
        **kwargs,
    ):
        try:
            order_sudo = self._document_check_access(
                "purchase.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        if order_sudo.state not in ("draft", "sent"):
            return False
        order_line = request.env["purchase.order.line"].sudo().browse(int(line_id))
        if order_line.order_id != order_sudo:
            return False
        if unlink:
            order_line.unlink()
            return False

        if input_price is not False:
            price = input_price
        else:
            number = -1 if remove else 1
            price = order_line.price_unit + number

        if price < 0:
            price = 0.0
        order_line.write({"price_unit": price})
        currency = order_sudo.currency_id
        format_price = partial(formatLang, request.env, digits=currency.decimal_places)

        results = {
            "order_line_price_unit": format_price(price),
            "order_line_price_total": format_price(order_line.price_total),
            "order_line_price_subtotal": format_price(order_line.price_subtotal),
            "order_amount_total": format_price(order_sudo.amount_total),
            "order_amount_untaxed": format_price(order_sudo.amount_untaxed),
        }
        try:
            results["order_totals_table"] = request.env["ir.ui.view"]._render_template(
                "purchase_rfq_online.purchase_order_portal_content_totals_table",
                {"purchase_order": order_sudo},
            )
        except ValueError:
            _logger.error("RFQ: error when updating purchase line")
        return results

    def _get_portal_editable_lines(self, order_sudo, line_ids):
        """
        Return the lines of ``order_sudo`` matching ``line_ids``.

        Any line belonging to another order is silently discarded, so a vendor
        can never write on a purchase order line he has no access to, even by
        forging the ids sent to the route.
        """
        try:
            line_ids = [int(line_id) for line_id in line_ids]
        except (TypeError, ValueError):
            return request.env["purchase.order.line"].sudo()
        return (
            request.env["purchase.order.line"]
            .sudo()
            .browse(line_ids)
            .exists()
            .filtered(lambda line: line.order_id == order_sudo)
        )

    @http.route(
        ["/my/purchase/<int:order_id>/update_vendor_part_no"],
        type="json",
        auth="public",
        website=True,
    )
    def po_line_update_vendor_part_no(
        self,
        order_id,
        line_id=None,
        vendor_part_no=None,
        lines=None,
        access_token=None,
        **kwargs,
    ):
        """
        Store the vendor part number entered on the RFQ portal.

        Accepts either a single line (``line_id`` / ``vendor_part_no``) or a
        batch of them (``lines`` being a mapping of line id -> value), so the
        values can be flushed in one call before the RFQ is signed and sent.
        """
        try:
            order_sudo = self._document_check_access(
                "purchase.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": request.env._("Invalid order.")}

        if not order_sudo._has_to_be_signed():
            return {"error": request.env._("This quotation can no longer be edited.")}

        values = dict(lines or {})
        if line_id is not None:
            values[line_id] = vendor_part_no

        order_lines = self._get_portal_editable_lines(order_sudo, values.keys())
        saved = {}
        for line in order_lines:
            part_no = values.get(line.id, values.get(str(line.id)))
            part_no = (part_no or "").strip()[:VENDOR_PART_NO_MAX_LENGTH]
            # Only the vendor part number is written here: the product and its
            # internal reference are left untouched.
            line.write({"vendor_part_no": part_no or False})
            saved[line.id] = line.vendor_part_no or ""

        return {"vendor_part_no": saved}

    @http.route(
        ["/my/purchase/<int:order_id>"], type="http", auth="public", website=True
    )
    def portal_my_purchase_order(self, order_id=None, access_token=None, **kw):
        response = super().portal_my_purchase_order(order_id, access_token, **kw)
        if response.qcontext.get("order") and not kw.get("report_type"):
            purchase_order = response.qcontext["order"]
            response.qcontext["purchase_order"] = purchase_order
            response.template = "purchase_rfq_online.purchase_order_portal_template"
            backend_url = (
                f"/web#model={purchase_order._name}"
                f"&id={purchase_order.id}"
                f"&action={purchase_order._get_portal_return_action().id}"
                f"&view_type=form"
            )
            response.qcontext["backend_url"] = backend_url
            response.qcontext["vendor_part_no_max_length"] = VENDOR_PART_NO_MAX_LENGTH
        if kw.get("message"):
            response.qcontext["message"] = kw["message"]
        return response

    @http.route(
        ["/my/purchase/<int:order_id>/accept"], type="json", auth="public", website=True
    )
    def purchase_order_rfq_accept(
        self, order_id, access_token=None, name=None, signature=None
    ):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get("access_token")
        try:
            order_sudo = self._document_check_access(
                "purchase.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": request.env._("Invalid order.")}

        if not signature:
            return {"error": request.env._("Signature is missing.")}

        if order_sudo.state not in ("draft", "sent"):
            query_string = "&message=cant_sign"
            return {
                "force_refresh": True,
                "redirect_url": order_sudo.get_portal_url(query_string=query_string),
            }

        try:
            order_sudo.write(
                {
                    "signed_by": name,
                    "signed_on": fields.Datetime.now(),
                    "signature": signature,
                }
            )
        except (TypeError, binascii.Error):
            return {"error": request.env._("Invalid signature data.")}

        pdf = (
            request.env["ir.actions.report"]
            .sudo()
            ._render_qweb_pdf("purchase.action_report_purchase_order", [order_sudo.id])[
                0
            ]
        )

        author = (
            order_sudo.partner_id
            if request.env.user._is_public()
            else request.env.user.partner_id
        )
        order_sudo.message_post(
            author_id=author.id,
            body=request.env._("Quotation is signed by %s", name),
            subtype_xmlid="purchase_rfq_online.mt_rfq_signed",
            attachments=[(f"{order_sudo.name}.pdf", pdf)],
        )

        query_string = "&message=sign_ok"
        redirect_url = order_sudo.get_portal_url(query_string=query_string)
        return {
            "force_refresh": True,
            "redirect_url": redirect_url,
        }

    @http.route(
        ["/my/purchase/<int:order_id>/decline"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def purchase_order_rfq_decline(self, order_id, access_token=None, **post):
        try:
            order_sudo = self._document_check_access(
                "purchase.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        message = post.get("decline_message")

        query_string = False
        if message:
            order_sudo.button_cancel()
            author = (
                order_sudo.partner_id
                if request.env.user._is_public()
                else request.env.user.partner_id
            )
            order_sudo.message_post(
                author_id=author.id,
                body=message,
                subtype_xmlid="purchase_rfq_online.mt_rfq_declined",
            )
        else:
            query_string = "&message=cant_reject"

        return request.redirect(order_sudo.get_portal_url(query_string=query_string))

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        PurchaseOrder = request.env["purchase.order"]
        if "purchase_count" in counters:
            values["purchase_count"] = (
                PurchaseOrder.search_count(
                    [("state", "in", ["sent", "purchase", "done", "cancel"])]
                )
                if PurchaseOrder.has_access("read")
                else 0
            )
        return values
