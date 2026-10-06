/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const OPTIONS = [
    { key: "g", label: "G", title: "Good" },
    { key: "w", label: "W", title: "Warning" },
    { key: "b", label: "B", title: "Bad" },
];

/**
 * 50 Points result cell.
 *  - Normal items: G / W / B segmented control on `condition` (grey until picked).
 *  - Miscellaneous items (is_yes_no): plain on/off switch on `check_mark`.
 */
export class GwbToggleField extends Component {
    static template = "job_card_extension.GwbToggleField";
    static props = { ...standardFieldProps };

    get options() {
        return OPTIONS;
    }
    get data() {
        return this.props.record.data;
    }
    get isYesNo() {
        return !!this.data.is_yes_no;
    }
    get value() {
        return this.data[this.props.name] || false;
    }
    get checked() {
        return !!this.data.check_mark;
    }

    async onSelect(key) {
        if (this.props.readonly) {
            return;
        }
        // Tapping the active option again clears it back to grey.
        const next = this.value === key ? false : key;
        await this.props.record.update({ [this.props.name]: next });
    }

    async onToggle() {
        if (this.props.readonly) {
            return;
        }
        await this.props.record.update({ check_mark: !this.checked });
    }
}

registry.category("fields").add("gwb_toggle", {
    component: GwbToggleField,
    displayName: "G / W / B Toggle",
    supportedTypes: ["selection"],
    fieldDependencies: [
        { name: "is_yes_no", type: "boolean" },
        { name: "check_mark", type: "boolean" },
    ],
});
