/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";

import { MulkiyaScanDialog } from "./mulkiya_scan_dialog";

/**
 * "Scan Mulkiya (OCR)" button for the vehicle form.
 *
 * Implemented as a view widget rather than a server button so that it also
 * works while the vehicle is being created: the extracted values are written
 * into the open form, not into the database.
 */
export class MulkiyaScanButton extends Component {
    static template = "odex_mulkiya_scan_fleet.ScanButton";

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get record() {
        return this.props.record;
    }

    onClick() {
        const record = this.record;
        const resId = record.resId || false;
        this.dialog.add(MulkiyaScanDialog, {
            title: _t("Scan Mulkiya (OCR)"),
            vehicleId: resId,
            sourceReference: resId ? `${record.resModel},${resId}` : "fleet.vehicle,new",
            onApply: async (formValues) => {
                await this.applyToForm(formValues);
            },
        });
    }

    async applyToForm(formValues) {
        const record = this.record;
        const values = {};
        const ignored = [];
        for (const [fieldName, value] of Object.entries(formValues || {})) {
            const field = record.fields[fieldName];
            if (!field) {
                ignored.push(fieldName);
                continue;
            }
            if (field.type === "many2one") {
                values[fieldName] = value
                    ? { id: value.id, display_name: value.display_name }
                    : false;
            } else {
                values[fieldName] = value;
            }
        }
        if (Object.keys(values).length) {
            await record.update(values);
        }
        if (ignored.length) {
            this.notification.add(
                _t("These fields are not on this form: %s", ignored.join(", ")),
                { type: "warning" }
            );
        }
    }
}

export const mulkiyaScanButton = {
    component: MulkiyaScanButton,
};

registry.category("view_widgets").add("mulkiya_scan_button", mulkiyaScanButton);
