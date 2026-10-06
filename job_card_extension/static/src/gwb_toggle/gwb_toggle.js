/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const OPTIONS = [
    { key: "g", label: "G", title: "Good" },
    { key: "w", label: "W", title: "Warning" },
    { key: "b", label: "B", title: "Bad" },
];

export class GwbToggleField extends Component {
    static template = "job_card_extension.GwbToggleField";
    static props = { ...standardFieldProps };

    get options() {
        return OPTIONS;
    }

    get value() {
        return this.props.record.data[this.props.name] || false;
    }

    async onSelect(key) {
        if (this.props.readonly) {
            return;
        }
        // Clicking the active option again clears it back to grey.
        const next = this.value === key ? false : key;
        await this.props.record.update({ [this.props.name]: next });
    }
}

export const gwbToggleField = {
    component: GwbToggleField,
    displayName: "G / W / B Toggle",
    supportedTypes: ["selection"],
};

registry.category("fields").add("gwb_toggle", gwbToggleField);
