/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PortalSaleQtyEdit = publicWidget.Widget.extend({
    selector: "#sales_order_table",
    events: {
        "change .js_portal_so_qty": "_onChangeQty",
        "click .js_portal_so_confirm": "_onClickConfirm",
    },

    /**
     * Read order + token from the table data attributes
     */
    _getContext: function () {
        const $table = this.$el;
        return {
            orderId: $table.data("order-id"),
            token: $table.data("token"),
        };
    },

    /**
     * Paint a confirmation button - and its row - according to its state.
     * Mirrors exactly what the QWeb template renders on page load.
     */
    _renderConfirmState: function ($btn, confirmed) {
        confirmed = !!confirmed;
        $btn.toggleClass("tus_confirmed", confirmed);
        $btn.attr("data-confirmed", confirmed ? "1" : "0");
        $btn.attr("aria-pressed", confirmed ? "true" : "false");
        $btn.attr(
            "title",
            confirmed ? "Line confirmed by you" : "Click to confirm this line"
        );
        $btn.find(".js_portal_confirm_label").text(
            confirmed ? "Confirmed" : "Confirm"
        );
        $btn.closest("tr").toggleClass("tus_line_confirmed", confirmed);
    },

    /**
     * Swap in the freshly rendered summary (confirmed lines only) so the
     * customer sees the amount they are approving without a page reload.
     */
    _refreshTotals: function (totalsHtml) {
        if (!totalsHtml) {
            return;
        }
        const $wrapper = $("#tus_totals_wrapper");
        if ($wrapper.length) {
            $wrapper.html(totalsHtml);
        }
    },

    /**
     * On quantity change, call JSON route and then redirect.
     * The current checkbox state of the line is sent along, so it is stored
     * within the same save action.
     */
    _onChangeQty: async function (ev) {
        ev.preventDefault();
        const $input = $(ev.currentTarget);
        const lineId = $input.data("line-id");
        const qty = $input.val();

        const ctx = this._getContext();
        if (!ctx.orderId || !lineId) {
            console.error("Missing orderId or lineId in portal SO table.");
            return;
        }

        const $btn = this.$(`.js_portal_so_confirm[data-line-id="${lineId}"]`);
        const confirmed = $btn.length
            ? $btn.attr("data-confirmed") === "1"
            : null;

        try {
            const result = await rpc(`/my/orders/${ctx.orderId}/update_line_qty`, {
                line_id: lineId,
                quantity: qty,
                access_token: ctx.token,
                confirmed: confirmed,
            });

            if (!result || !result.success) {
                console.error("Error updating qty from portal:", result && result.error);
                return;
            }

            // redirect back to the portal order page
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                window.location.reload();
            }
        } catch (error) {
            console.error("RPC error while updating qty:", error);
        }
    },

    /**
     * Toggle the customer approval flag of a quotation line.
     * The UI updates immediately, then the state is persisted; on failure the
     * previous state is restored. Lines are never deleted.
     */
    _onClickConfirm: async function (ev) {
        ev.preventDefault();

        const $btn = $(ev.currentTarget);
        if ($btn.is(":disabled") || $btn.hasClass("tus_pending")) {
            return;
        }

        const lineId = $btn.data("line-id");
        const ctx = this._getContext();
        if (!ctx.orderId || !lineId) {
            console.error("Missing orderId or lineId in portal SO table (confirm).");
            return;
        }

        const previous = $btn.attr("data-confirmed") === "1";
        const target = !previous;

        // Optimistic UI update
        this._renderConfirmState($btn, target);
        $btn.addClass("tus_pending");

        try {
            const result = await rpc(
                `/my/orders/${ctx.orderId}/toggle_line_confirmed`,
                {
                    line_id: lineId,
                    confirmed: target,
                    access_token: ctx.token,
                }
            );

            if (!result || !result.success) {
                console.error(
                    "Error updating confirmation from portal:",
                    result && result.error
                );
                this._renderConfirmState($btn, previous);
                return;
            }

            this._renderConfirmState($btn, result.confirmed);
            this._refreshTotals(result.totals_html);
        } catch (error) {
            console.error("RPC error while updating confirmation:", error);
            this._renderConfirmState($btn, previous);
        } finally {
            $btn.removeClass("tus_pending");
        }
    },
});

export default publicWidget.registry.PortalSaleQtyEdit;
