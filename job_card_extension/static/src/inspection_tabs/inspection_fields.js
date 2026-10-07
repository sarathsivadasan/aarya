/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useInputField } from "@web/views/fields/input_field_hook";

/*
 * Pre Inspection / Final Inspection widgets.
 *
 * Both are editable in one tap while the list row (or mobile card) is NOT in edition:
 * extractProps keeps only the real readonly rules (closed job card, readonly attr), and
 * every pointer event is stopped on the widget so it never reaches the row / card.
 */
function extractDirectEditProps(fieldInfo, dynamicInfo) {
    return { readonly: dynamicInfo.readonly };
}

// ------------------------------------------------------------------ ON / OFF switch
export class JcOnOffField extends Component {
    static template = "job_card_extension.JcOnOffField";
    static props = {
        ...standardFieldProps,
        labelPosition: { type: String, optional: true },
    };
    static defaultProps = { labelPosition: "inside" };

    get checked() {
        return !!this.props.record.data[this.props.name];
    }

    async toggle() {
        if (this.props.readonly) {
            return;
        }
        await this.props.record.update({ [this.props.name]: !this.checked });
    }

    onKeydown(ev) {
        if (["space", "enter"].includes(getActiveHotkey(ev))) {
            ev.preventDefault();
            ev.stopPropagation();
            this.toggle();
        }
    }
}

registry.category("fields").add("jc_onoff", {
    component: JcOnOffField,
    displayName: _t("ON / OFF Switch"),
    supportedTypes: ["boolean"],
    supportedOptions: [
        {
            label: _t("Label position"),
            name: "label_position",
            type: "selection",
            choices: [
                { label: _t("Inside the switch"), value: "inside" },
                { label: _t("Beside the switch"), value: "outside" },
            ],
        },
    ],
    extractProps(fieldInfo, dynamicInfo) {
        return {
            ...extractDirectEditProps(fieldInfo, dynamicInfo),
            labelPosition: fieldInfo.options.label_position === "outside" ? "outside" : "inside",
        };
    },
});

// ------------------------------------------------------------------ Remark box
export class JcRemarkField extends Component {
    static template = "job_card_extension.JcRemarkField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.inputRef = useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            refName: "input",
            preventLineBreaks: true,
        });
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("jc_remark", {
    component: JcRemarkField,
    displayName: _t("Inspection Remark"),
    supportedTypes: ["char", "text"],
    extractProps(fieldInfo, dynamicInfo) {
        return {
            ...extractDirectEditProps(fieldInfo, dynamicInfo),
            placeholder: fieldInfo.placeholder || _t("Remark"),
        };
    },
});
