import publicWidget from "@web/legacy/js/public/public_widget";
import {rpc} from "@web/core/network/rpc";

/**
 * Saves the vendor part number (VPart No.) typed by the vendor on each RFQ
 * line of the purchase portal.
 *
 * The value is stored as soon as the input loses the focus, and any value
 * still pending is flushed before the quotation is signed, so "Sign & Send"
 * always sends the numbers currently displayed on screen.
 */
publicWidget.registry.MyPOVendorPartNo = publicWidget.Widget.extend({
    selector: ".o_portal_purchase_sidebar",
    events: {
        "change input.js_po_line_vendor_part_no": "_onChangeVendorPartNo",
    },

    /**
     * @override
     */
    init() {
        this._super.apply(this, arguments);
        this.rpc = rpc;
        this.onSignSubmitCapture = this._onSignSubmitCapture.bind(this);
    },

    /**
     * @override
     */
    start: function () {
        return this._super.apply(this, arguments).then(() => {
            // Capture phase: the values are flushed before the signature
            // component sends its own request.
            this.el.addEventListener("click", this.onSignSubmitCapture, true);
        });
    },

    /**
     * @override
     */
    destroy: function () {
        if (this.el) {
            this.el.removeEventListener("click", this.onSignSubmitCapture, true);
        }
        this._super.apply(this, arguments);
    },

    /**
     * Order id and access token of the quotation being displayed.
     *
     * They are read from the accept form already present in the page, so no
     * additional data has to be exposed in the template.
     *
     * @private
     * @returns {Object|false}
     */
    _getOrderParams: function () {
        const form = this.el.querySelector("form.js_accept_json");
        if (!form) {
            return false;
        }
        const orderId = parseInt(form.dataset.orderId, 10);
        if (!orderId) {
            return false;
        }
        const params = {};
        if (form.dataset.token) {
            params.access_token = form.dataset.token;
        }
        return {orderId: orderId, params: params};
    },

    /**
     * @private
     * @returns {Element[]} inputs whose value is not saved yet
     */
    _getPendingInputs: function () {
        return [...this.el.querySelectorAll("input.js_po_line_vendor_part_no")].filter(
            (input) => input.value !== (input.dataset.savedValue ?? input.defaultValue)
        );
    },

    /**
     * Sends the given inputs to the server and remembers the saved values.
     *
     * @private
     * @param {Element[]} inputs
     * @returns {Promise}
     */
    _saveVendorPartNo: function (inputs) {
        const order = this._getOrderParams();
        if (!order || !inputs.length) {
            return Promise.resolve();
        }
        const lines = {};
        for (const input of inputs) {
            const lineId = parseInt(input.dataset.id, 10);
            if (lineId) {
                lines[lineId] = input.value;
            }
        }
        const url = `/my/purchase/${order.orderId}/update_vendor_part_no`;
        return this.rpc(url, {...order.params, lines: lines}).then((data) => {
            if (!data || data.error) {
                return;
            }
            for (const input of inputs) {
                const saved = data.vendor_part_no[input.dataset.id];
                if (saved !== undefined) {
                    input.value = saved;
                    input.dataset.savedValue = saved;
                }
            }
        });
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onChangeVendorPartNo: function (ev) {
        return this._saveVendorPartNo([ev.currentTarget]);
    },

    /**
     * Flushes the pending values before letting the signature component
     * submit the quotation.
     *
     * @private
     * @param {Event} ev
     */
    _onSignSubmitCapture: function (ev) {
        const button = ev.target.closest(".o_portal_sign_submit");
        if (!button || button.dataset.vendorPartNoFlushed) {
            return;
        }
        const pending = this._getPendingInputs();
        if (!pending.length) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this._saveVendorPartNo(pending).then(
            () => this._replaySignClick(button),
            () => this._replaySignClick(button)
        );
    },

    /**
     * @private
     * @param {Element} button
     */
    _replaySignClick: function (button) {
        button.dataset.vendorPartNoFlushed = "1";
        button.click();
        delete button.dataset.vendorPartNoFlushed;
    },
});

export default publicWidget.registry.MyPOVendorPartNo;
