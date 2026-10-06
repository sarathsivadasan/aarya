/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const OPTIONS = [
    { key: "g", label: "G", aria: "Good" },
    { key: "w", label: "W", aria: "Warning" },
    { key: "b", label: "B", aria: "Bad" },
];

/**
 * 50 Points result cell.
 *  - Normal items: G / W / B buttons on `condition` (grey until picked).
 *  - Miscellaneous items (is_yes_no): Odoo's standard green toggle on `check_mark`.
 */
export class GwbToggleField extends Component {
    static template = "job_card_extension.GwbToggleField";
    static components = { CheckBox };
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
        // Clicking the active option again clears it back to grey.
        const next = this.value === key ? false : key;
        await this.props.record.update({ [this.props.name]: next });
    }

    async onToggle(value) {
        if (this.props.readonly) {
            return;
        }
        await this.props.record.update({ check_mark: !!value });
    }
}

/*
 * Odoo makes every field widget readonly while its list row (or x2many kanban card)
 * is not in edition, so a first click is spent opening the row. Returning `readonly`
 * from extractProps keeps only the real readonly rules (field attr, closed job card,
 * non-editable list) - the same trick core uses for the priority widget - so one
 * click on G / W / B or on a toggle sets the value directly.
 */
function extractDirectEditProps(fieldInfo, dynamicInfo) {
    return { readonly: dynamicInfo.readonly };
}

registry.category("fields").add("gwb_toggle", {
    component: GwbToggleField,
    displayName: "G / W / B Toggle",
    supportedTypes: ["selection"],
    extractProps: extractDirectEditProps,
    fieldDependencies: [
        { name: "is_yes_no", type: "boolean" },
        { name: "check_mark", type: "boolean" },
    ],
});

/**
 * jc_toggle: Odoo's green boolean toggle, clickable in one tap in any list row / card.
 */
export class JcToggleField extends Component {
    static template = "job_card_extension.JcToggleField";
    static components = { CheckBox };
    static props = { ...standardFieldProps };

    get checked() {
        return !!this.props.record.data[this.props.name];
    }

    async onToggle(value) {
        if (this.props.readonly) {
            return;
        }
        await this.props.record.update({ [this.props.name]: !!value });
    }
}

registry.category("fields").add("jc_toggle", {
    component: JcToggleField,
    displayName: "Job Card Toggle",
    supportedTypes: ["boolean"],
    extractProps: extractDirectEditProps,
});
