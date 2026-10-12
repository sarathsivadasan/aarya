/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { serializeDate } from "@web/core/l10n/dates";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Time-slot picker for the booking form.
 *
 * Lists the free times of the chosen date (from the live working schedule)
 * as buttons. Picking one writes its start hour into the float field the
 * widget is attached to (pick_hour); the model turns date + hour into the
 * real slot when the booking is saved.
 */
export class BookingSlotPicker extends Component {
    static template = "odex_workshop_booking.BookingSlotPicker";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ slots: [], message: "", loading: false });
        this._key = null;
        onWillStart(() => this.load(this.props));
        onWillUpdateProps((next) => this.load(next));
    }

    get current() {
        return this.props.record.data[this.props.name] || 0;
    }

    isSelected(slot) {
        return this.current > 0 && Math.abs(slot.hour_from - this.current) < 0.0001;
    }

    async load(props) {
        const data = props.record.data;
        const date = data.pick_date ? serializeDate(data.pick_date) : false;
        const company = data.company_id ? data.company_id[0] : false;
        const key = `${company}|${date}|${props.record.resId}`;
        if (key === this._key) {
            return;
        }
        this._key = key;
        if (!date) {
            this.state.slots = [];
            this.state.message = "";
            return;
        }
        this.state.loading = true;
        try {
            const res = await this.orm.call("odex.workshop.booking", "get_free_times", [
                company,
                date,
                props.record.resId || false,
            ]);
            this.state.slots = res.slots;
            this.state.message = res.message;
        } finally {
            this.state.loading = false;
        }
        // A time that does not exist on the newly chosen date must not linger.
        const hour = data[props.name] || 0;
        if (
            !props.readonly &&
            hour > 0 &&
            !this.state.slots.some(
                (s) => s.bookable && Math.abs(s.hour_from - hour) < 0.0001
            )
        ) {
            await props.record.update({ [props.name]: 0 });
        }
    }

    async select(slot) {
        if (this.props.readonly || !slot.bookable) {
            return;
        }
        await this.props.record.update({ [this.props.name]: slot.hour_from });
    }
}

registry.category("fields").add("booking_slot_picker", {
    component: BookingSlotPicker,
    supportedTypes: ["float"],
    displayName: "Booking Time Slots",
});
