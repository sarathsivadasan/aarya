/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.OdexPortalBookingDetail = publicWidget.Widget.extend({
    selector: "#owb_portal_detail",
    events: {
        "change #owb_rs_date": "_onDateChange",
        "click .owb-slot.owb-slot-bookable": "_onSlotClick",
        "click #owb_rs_confirm": "_onConfirm",
    },

    start() {
        this.slotId = null;
        // The date input is prefilled with the current booking date, so load
        // its slots immediately instead of making the customer re-pick it.
        const input = this.el.querySelector("#owb_rs_date");
        if (input && input.value) {
            this._loadSlots(input.value);
        }
        return this._super(...arguments);
    },

    async _onDateChange(ev) {
        await this._loadSlots(ev.currentTarget.value);
    },

    async _loadSlots(date) {
        const container = this.el.querySelector("#owb_rs_slots");
        if (!date || !container) return;
        container.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div>';
        const result = await rpc("/booking/api/slots", {
            company_id: parseInt(this.el.dataset.companyId), date,
        });
        container.innerHTML = "";
        this.slotId = null;
        this.el.querySelector("#owb_rs_confirm").disabled = true;
        const slots = (result.slots || []).filter((s) => s.bookable);
        if (!slots.length) {
            container.innerHTML = '<div class="text-muted small">No available slots on this date.</div>';
            return;
        }
        for (const slot of slots) {
            const el = document.createElement("div");
            el.className = `owb-slot owb-slot-${slot.state} owb-slot-bookable`;
            el.dataset.slotId = slot.id;
            el.innerHTML = `<div class="fw-semibold">${slot.label}</div>
                <div class="owb-slot-state">${slot.state === "limited" ? "Limited" : "Available"}</div>`;
            container.appendChild(el);
        }
    },

    _onSlotClick(ev) {
        const el = ev.currentTarget;
        this.slotId = parseInt(el.dataset.slotId);
        this.el.querySelectorAll(".owb-slot").forEach((s) =>
            s.classList.toggle("owb-slot-selected", s === el));
        this.el.querySelector("#owb_rs_confirm").disabled = false;
    },

    async _onConfirm() {
        if (!this.slotId) return;
        const btn = this.el.querySelector("#owb_rs_confirm");
        const errorBox = this.el.querySelector("#owb_rs_error");
        errorBox.classList.add("d-none");
        btn.disabled = true;
        const bookingId = parseInt(this.el.dataset.bookingId);
        const result = await rpc(`/my/bookings/${bookingId}/reschedule`, {
            booking_id: bookingId, slot_id: this.slotId,
        });
        if (result.success) {
            window.location.reload();
            return;
        }
        errorBox.textContent = result.error || "Could not reschedule. Please try again.";
        errorBox.classList.remove("d-none");
        btn.disabled = false;
    },
});

publicWidget.registry.OdexPortalVehicles = publicWidget.Widget.extend({
    selector: "#owbAddVehicleModal",
    events: {
        "change #owb_pv_make": "_onMakeChange",
    },

    async _onMakeChange(ev) {
        const brandId = ev.currentTarget.value;
        const modelSelect = this.el.querySelector("#owb_pv_model");
        modelSelect.innerHTML = '<option value="">Select Model</option>';
        modelSelect.disabled = !brandId;
        if (!brandId) return;
        const result = await rpc("/booking/api/models", { brand_id: brandId });
        for (const m of result.models || []) {
            const opt = document.createElement("option");
            opt.value = m.id;
            opt.textContent = m.name;
            modelSelect.appendChild(opt);
        }
    },
});
