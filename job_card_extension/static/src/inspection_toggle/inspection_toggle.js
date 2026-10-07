/** @odoo-module **/
/*
 * Inspection ON/OFF toggles on the job card.
 *
 * Root cause of "toggle only works after selecting the row":
 * inside an editable one2many list Odoo renders the boolean_toggle with
 * ListBooleanToggleField, whose onClick() only flips the value when the row
 * is already in edition (record.isInEdition). The first click on a row that
 * is not selected is ignored by the toggle and then bubbles up to the list
 * cell, which only selects the row. The second click finally toggles.
 *
 * Fix:
 *  1. odex_onoff_toggle: ON/OFF switch used by the Pre/Final Inspection tabs.
 *     It decides "editable?" from the form + field modifiers (not from the
 *     row being selected), updates the line directly and stops the click from
 *     reaching the row.
 *  2. The same rule is applied to the standard list boolean_toggle, but only
 *     for one2many lines inside a project.task form (job card / inspection),
 *     so the existing 50 Points Miscellaneous Inspection toggles behave the
 *     same without touching other apps.
 */
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { Component } from "@odoo/owl";

function parentForm(record) {
    const root = record?.model?.root;
    // A form record has .data; a list view root (DynamicList) does not.
    if (!root || root === record || !root.data || typeof root.isInEdition !== "boolean") {
        return null;
    }
    return root;
}

/** Can this x2many line's boolean be changed right now, selected or not? */
export function isLineToggleReadonly(record, name, propsReadonly) {
    const root = parentForm(record);
    if (!root) {
        return !!propsReadonly;
    }
    if (!root.isInEdition || root.data.is_close) {
        return true;
    }
    if (record.isInEdition) {
        return !!propsReadonly;
    }
    const expr = record.activeFields?.[name]?.readonly;
    if (!expr || expr === "False" || expr === "0") {
        return false;
    }
    if (expr === "True" || expr === "1") {
        return true;
    }
    try {
        return !!evaluateBooleanExpr(expr, record.evalContextWithVirtualIds || record.evalContext);
    } catch {
        return true;
    }
}

export class OdexOnOffToggle extends Component {
    static template = "job_card_extension.OdexOnOffToggle";

    get value() {
        return !!this.props.record.data[this.props.name];
    }
    get isReadonly() {
        return isLineToggleReadonly(this.props.record, this.props.name, this.props.readonly);
    }
    async onClick(ev) {
        // Never let the click reach the list cell/row (no row selection needed).
        ev.stopPropagation();
        ev.preventDefault();
        if (this.isReadonly) {
            return;
        }
        await this.props.record.update({ [this.props.name]: !this.value });
    }
}

const onOffToggle = {
    component: OdexOnOffToggle,
    displayName: "ON/OFF Toggle",
    supportedTypes: ["boolean"],
    isEmpty: () => false,
};
const fieldRegistry = registry.category("fields");
fieldRegistry.add("odex_onoff_toggle", onOffToggle);
fieldRegistry.add("list.odex_onoff_toggle", onOffToggle);

// Same behaviour for the standard boolean_toggle inside job card sub-lists.
const listToggle = fieldRegistry.get("list.boolean_toggle", null);
if (listToggle && listToggle.component) {
    patch(listToggle.component.prototype, {
        async onClick(ev) {
            const record = this.props.record;
            const root = parentForm(record);
            if (root && root.resModel === "project.task" && !record.isInEdition) {
                ev?.stopPropagation?.();
                ev?.preventDefault?.();
                if (!isLineToggleReadonly(record, this.props.name, this.props.readonly)) {
                    await record.update({ [this.props.name]: !record.data[this.props.name] });
                }
                return;
            }
            return super.onClick(...arguments);
        },
    });
}
