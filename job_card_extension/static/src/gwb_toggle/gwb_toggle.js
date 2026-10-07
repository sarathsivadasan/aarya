/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
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

    onSwitchClick() {
        return this.onToggle(!this.checked);
    }

    onSwitchKeydown(ev) {
        if (["space", "enter"].includes(getActiveHotkey(ev))) {
            ev.preventDefault();
            ev.stopPropagation();
            this.onSwitchClick();
        }
    }
}

/*
 * Why a row had to be selected before the toggle reacted
 * -------------------------------------------------------
 * 1. Odoo makes every field widget readonly while its list row (or x2many kanban card)
 *    is not in edition, and core's CheckBox renders that as <input disabled>. Browsers
 *    swallow clicks on disabled form controls (no click / change event at all), so the
 *    first tap did nothing on the switch and only the row behind it opened.
 * 2. The <label for> of CheckBox re-dispatches a second click on the input; inside an
 *    x2many row that synthetic click bubbles to the cell and can toggle the row into
 *    edition instead of flipping the value.
 *
 * Fix: (a) extractProps below keeps only the real readonly rules, and (b) the switch is
 * now drawn as a plain, non-interactive form-switch (pointer-events: none on the input,
 * no label) wrapped in one role="switch" element that owns the click / tap / keyboard
 * and stops it from reaching the row. Same Odoo green toggle look.
 *
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

    onSwitchClick() {
        return this.onToggle(!this.checked);
    }

    onSwitchKeydown(ev) {
        if (["space", "enter"].includes(getActiveHotkey(ev))) {
            ev.preventDefault();
            ev.stopPropagation();
            this.onSwitchClick();
        }
    }
}

registry.category("fields").add("jc_toggle", {
    component: JcToggleField,
    displayName: "Job Card Toggle",
    supportedTypes: ["boolean"],
    extractProps: extractDirectEditProps,
});
