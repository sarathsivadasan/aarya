/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { captureImage } from "./camera";

/**
 * Field widget rendered beside Registration No. (plate) and Chassis No. (Mulkiya).
 * It is an ACTION BUTTON on the field - never a separate card.
 */
export class OcrScanWidget extends Component {
    static template = "odex_vehicle_gate_pass.OcrScan";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            busy: false,
            preview: null, // {values, matchName}
        });
        this.kind = (this.props.options && this.props.options.kind) || "plate";
    }

    get label() {
        return this.kind === "mulkiya" ? _t("Scan VIN") : _t("Scan Plate");
    }

    get recordId() {
        return this.props.record.resId;
    }

    async onScan() {
        if (!this.recordId) {
            this.notification.add(_t("Save the gate pass before scanning."), { type: "warning" });
            return;
        }
        const status = await rpc("/odex_gate_pass/ocr/status", {});
        if (!status.available) {
            this.notification.add(status.message || _t("OCR service is not configured."), {
                type: "warning",
            });
            return;
        }
        const image = await captureImage();
        if (!image) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await rpc("/odex_gate_pass/ocr/scan", {
                gate_pass_id: this.recordId,
                image,
                kind: this.kind,
            });
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            if (!result.found) {
                this.notification.add(
                    _t("Nothing could be read from this image. Try again in better light."),
                    { type: "warning" }
                );
                return;
            }
            const values = this._extractValues(result);
            this.state.preview = {
                values,
                headline:
                    this.kind === "mulkiya"
                        ? values.chassis_no || values.registration_no
                        : values.registration_no,
                matchName: result.match && result.match.found ? result.match.display_name : null,
            };
        } finally {
            this.state.busy = false;
        }
    }

    _extractValues(result) {
        const keys = [
            "registration_no",
            "chassis_no",
            "engine_no",
            "brand",
            "vehicle_model",
            "manufacturing_year",
            "color",
            "fuel_type",
            "transmission",
            "plate_source",
        ];
        const values = {};
        for (const key of keys) {
            if (result[key]) {
                values[key] = result[key];
            }
        }
        return values;
    }

    async onConfirm() {
        const values = this.state.preview.values;
        this.state.busy = true;
        try {
            const applied = await rpc("/odex_gate_pass/ocr/apply", {
                gate_pass_id: this.recordId,
                values,
            });
            if (applied.error) {
                this.notification.add(applied.error, { type: "danger" });
                return;
            }
            await this.props.record.load();
            this.props.record.model.notify();
            if (applied.vehicle_found) {
                this.notification.add(
                    _t("Matched %s from the fleet.", applied.vehicle_name),
                    { type: "success" }
                );
            } else {
                this.notification.add(_t("Detected values saved. No fleet vehicle matched yet."), {
                    type: "info",
                });
            }
        } finally {
            this.state.busy = false;
            this.state.preview = null;
        }
    }

    onRetry() {
        this.state.preview = null;
        this.onScan();
    }

    onCancel() {
        this.state.preview = null;
    }
}

export const ocrScanWidget = {
    component: OcrScanWidget,
    extractProps: ({ options }) => ({ options }),
    // supportedTypes: ["char"],
};

registry.category("view_widgets").add("odex_ocr_scan", ocrScanWidget);
