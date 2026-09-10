/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/** Horizontal workflow bar driven by the computed flow_json field. */
export class GatePassFlow extends Component {
    static template = "odex_vehicle_gate_pass.Flow";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
    }

    get steps() {
        const raw = this.props.record.data.flow_json;
        if (!raw) {
            return [];
        }
        try {
            return JSON.parse(raw);
        } catch (error) {
            return [];
        }
    }

    async onStepClick(step) {
        if (!step.clickable) {
            return;
        }
        if (!this.props.record.resId || this.props.record.isDirty) {
            await this.props.record.save();
        }
        try {
            await this.props.record.model.orm.call("odex.gate.pass", "action_flow_step", [
                [this.props.record.resId],
                step.key,
            ]);
            await this.props.record.load();
            this.props.record.model.notify();
        } catch (error) {
            // Odoo surfaces the UserError dialog itself; nothing more to do here.
            throw error;
        }
    }
}
export const gatePassFlow = { component: GatePassFlow };
registry.category("view_widgets").add("odex_gp_flow", gatePassFlow);

/** Booking status card. */
export class BookingStatus extends Component {
    static template = "odex_vehicle_gate_pass.BookingStatus";
    static props = ["*"];

    get data() {
        const record = this.props.record.data;
        return {
            status: record.booking_status,
            label: this._label(record.booking_status),
            no: record.booking_no,
            date: record.booking_date,
        };
    }
    _label(status) {
        return {
            booked: _t("BOOKED"),
            not_booked: _t("NOT BOOKED"),
            cancelled: _t("CANCELLED"),
        }[status] || _t("NOT BOOKED");
    }
}
export const bookingStatus = { component: BookingStatus };
registry.category("view_widgets").add("odex_gp_booking_status", bookingStatus);

/** Payment status card. */
export class PaymentStatus extends Component {
    static template = "odex_vehicle_gate_pass.PaymentStatus";
    static props = ["*"];

    get data() {
        const record = this.props.record.data;
        return {
            status: record.payment_status,
            label: this._label(record.payment_status),
            invoice: record.invoice_amount,
            paid: record.paid_amount,
            due: record.due_amount,
        };
    }
    _label(status) {
        return {
            paid: _t("PAID"),
            partial: _t("PARTIAL"),
            unpaid: _t("UNPAID"),
            not_invoiced: _t("NOT INVOICED"),
        }[status] || _t("NOT INVOICED");
    }
}
export const paymentStatus = { component: PaymentStatus };
registry.category("view_widgets").add("odex_gp_payment_status", paymentStatus);

/** Realistic round fuel gauge: red needle sweeps the top from E (lower-left) to F (lower-right). */
export class FuelGauge extends Component {
    static template = "odex_vehicle_gate_pass.FuelGauge";
    static props = ["*"];

    // Needle angle per level (degrees, 0 = right, CCW positive), sweeping over the top.
    get levels() {
        return [
            { key: "empty", label: "Empty", angle: 216 },
            { key: "quarter", label: "1/4", angle: 153 },
            { key: "half", label: "1/2", angle: 90 },
            { key: "three_quarter", label: "3/4", angle: 27 },
            { key: "full", label: "Full", angle: -36 },
        ];
    }
    get value() {
        return this.props.record.data[this.props.name] || "half";
    }
    get current() {
        return this.levels.find((level) => level.key === this.value) || this.levels[2];
    }
    _point(angle, radius) {
        const rad = (angle * Math.PI) / 180;
        return { x: 110 + radius * Math.cos(rad), y: 110 - radius * Math.sin(rad) };
    }
    get needle() {
        return this._point(this.current.angle, 74);
    }
    get needleTail() {
        return this._point(this.current.angle + 180, 16);
    }
    get ticks() {
        // Minor ticks around the top arc, plus the five level positions.
        const out = [];
        for (let i = 0; i <= 10; i++) {
            const angle = 216 - (i * 252) / 10; // 216 -> -36
            const inner = this._point(angle, 82);
            const outer = this._point(angle, i % 2 === 0 ? 94 : 90);
            out.push({ x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y, major: i % 2 === 0 });
        }
        return out;
    }
    get bigLabel() {
        return this.current.label;
    }
    async onSelect(key) {
        await this.props.record.update({ [this.props.name]: key });
    }
}
export const fuelGauge = {
    component: FuelGauge,
    supportedTypes: ["selection"],
};
registry.category("fields").add("odex_fuel_gauge", fuelGauge);

/** Timeline tab. */
export class TimelineWidget extends Component {
    static template = "odex_vehicle_gate_pass.Timeline";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.rows = [];
        this._load();
    }
    get recordId() {
        return this.props.record.resId;
    }
    async _load() {
        if (!this.recordId) {
            return;
        }
        this.rows = await this.orm.searchRead(
            "odex.gate.pass.timeline",
            [["gate_pass_id", "=", this.recordId]],
            ["step", "status", "date_label", "user_id", "note"],
            { order: "sequence" }
        );
        this.render();
    }
}
export const timelineWidget = { component: TimelineWidget };
registry.category("view_widgets").add("odex_timeline", timelineWidget);
