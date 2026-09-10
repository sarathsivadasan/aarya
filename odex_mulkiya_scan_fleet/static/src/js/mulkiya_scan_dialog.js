/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, useState } from "@odoo/owl";

const SUPPORTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_MB = 12;

/**
 * Mulkiya scanner dialog.
 *
 * Runs entirely against the scan model, never against the vehicle: the values
 * are handed back to the caller so they can be pushed into a form that has not
 * been saved yet.
 */
export class MulkiyaScanDialog extends Component {
    static template = "odex_mulkiya_scan_fleet.ScanDialog";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            front: null,
            back: null,
            step: "upload", // upload | scanning | result
            scanId: false,
            scanNumber: "",
            fields: [],
            warnings: {},
            threshold: 90,
            error: null,
            applying: false,
            simulated: false,
            options: {},
        });

        onWillStart(async () => {
            this.state.options = await this.orm.call(
                "odex.mulkiya.scan",
                "get_field_options",
                []
            );
        });
    }

    /**
     * Options offered for one field. The model list is narrowed down to the
     * selected make, so creating a vehicle cannot pick a model that belongs to
     * another brand.
     */
    optionsFor(field) {
        const options = this.state.options[field.key] || [];
        if (!options.length) {
            return null;
        }
        let available = options;
        const parentKey = options[0].parent_key;
        if (parentKey) {
            const parent = this.state.fields.find((f) => f.key === parentKey);
            if (parent && parent.record_id) {
                const narrowed = options.filter(
                    (option) => option.parent_id === parent.record_id
                );
                if (narrowed.length) {
                    available = narrowed;
                }
            }
        }
        // Keep whatever the OCR read, even when it is not in the master data:
        // the user must be able to see and keep the scanned value.
        if (field.value && !available.some((option) => option.name === field.value)) {
            return [{ id: false, name: field.value, unknown: true }, ...available];
        }
        return available;
    }

    isUnknown(field) {
        const options = this.state.options[field.key] || [];
        return Boolean(
            field.value &&
                options.length &&
                !options.some((option) => option.name === field.value)
        );
    }

    get canScan() {
        return Boolean(this.state.front && this.state.back) && !this.isBusy;
    }

    get isBusy() {
        return this.state.step === "scanning" || this.state.applying;
    }

    get columns() {
        // Three balanced columns, matching the Extracted Information layout.
        const fields = this.state.fields;
        const size = Math.ceil(fields.length / 3) || 1;
        return [
            fields.slice(0, size),
            fields.slice(size, size * 2),
            fields.slice(size * 2),
        ];
    }

    // ------------------------------------------------------------------
    // Images
    // ------------------------------------------------------------------
    onPick(side, ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file) {
            return;
        }
        if (!SUPPORTED_TYPES.includes(file.type)) {
            this.notification.add(_t("Only JPEG, PNG and WEBP images are supported."), {
                type: "warning",
            });
            return;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            this.notification.add(
                _t("This image is larger than %s MB. Please use a smaller picture.", MAX_MB),
                { type: "warning" }
            );
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            this.state[side] = reader.result;
        };
        reader.onerror = () => {
            this.notification.add(_t("The image could not be read."), { type: "danger" });
        };
        reader.readAsDataURL(file);
    }

    onDrop(side, ev) {
        ev.preventDefault();
        const file = ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) {
            this.onPick(side, { target: { files: [file], value: "" } });
        }
    }

    onRemove(side) {
        this.state[side] = null;
    }

    // ------------------------------------------------------------------
    // Scanning
    // ------------------------------------------------------------------
    async onScan() {
        if (!this.canScan) {
            this.notification.add(
                _t("Please upload both front and back sides before scanning."),
                { type: "warning" }
            );
            return;
        }
        this.state.step = "scanning";
        this.state.error = null;
        try {
            const result = await this.orm.call(
                "odex.mulkiya.scan",
                "scan_from_images",
                [
                    this.state.front.split(",")[1],
                    this.state.back.split(",")[1],
                    this.props.sourceReference || false,
                    this.props.vehicleId || false,
                ]
            );
            this.applyPayload(result);
        } catch (error) {
            this.state.step = "upload";
            throw error;
        }
    }

    applyPayload(payload) {
        if (!payload || !payload.success) {
            this.state.step = "upload";
            this.state.error =
                (payload && payload.error) ||
                _t("Unable to process the Mulkiya. Please try again.");
            return;
        }
        this.state.scanId = payload.scan_id;
        this.state.scanNumber = payload.scan_number;
        this.state.fields = payload.fields || [];
        this.state.warnings = payload.warnings || {};
        this.state.threshold = payload.threshold || 90;
        this.state.simulated = Boolean(payload.simulated);
        this.state.error = null;
        this.state.step = "result";
    }

    onRescan() {
        this.state.step = "upload";
        this.state.fields = [];
        this.state.warnings = {};
    }

    onFieldInput(field, ev) {
        field.value = ev.target.value;
        field.record_id = false;
        field.edited = true;
    }

    onFieldSelect(field, ev) {
        const options = this.optionsFor(field) || [];
        const index = parseInt(ev.target.value, 10);
        const option = Number.isNaN(index) || index < 0 ? null : options[index];
        // Index -1 is the "not detected" placeholder: clear rather than guess.
        field.value = option ? option.name : "";
        field.record_id = option && option.id ? option.id : false;
        field.matched = Boolean(field.record_id);
        field.edited = true;
        if (field.key === "make") {
            // A different make invalidates the model picked under the old one.
            const model = this.state.fields.find((f) => f.key === "model");
            if (model) {
                model.record_id = false;
            }
        }
    }

    confidenceClass(field) {
        if (!field.confidence) {
            return "text-bg-light text-muted";
        }
        return field.confidence < this.state.threshold
            ? "text-bg-warning"
            : "text-bg-success";
    }

    // ------------------------------------------------------------------
    // Update the form
    // ------------------------------------------------------------------
    async onUpdate() {
        if (this.state.applying) {
            return;
        }
        this.state.applying = true;
        try {
            const edited = {};
            const selected = {};
            for (const field of this.state.fields) {
                edited[field.key] = field.value;
                if (field.record_id) {
                    selected[field.key] = field.record_id;
                }
            }
            const result = await this.orm.call(
                "odex.mulkiya.scan",
                "apply_to_form",
                [
                    [this.state.scanId],
                    edited,
                    this.props.vehicleId || false,
                    selected,
                ]
            );
            if (!result.success) {
                this.state.error = result.error;
                return;
            }
            await this.props.onApply(result.form_values, this.state.scanId);
            if (result.skipped && result.skipped.length) {
                this.notification.add(result.skipped.join("\n"), {
                    title: _t("Some values were not applied"),
                    type: "warning",
                    sticky: true,
                });
            } else {
                this.notification.add(
                    _t("Vehicle information applied. Remember to save the vehicle."),
                    { type: "success" }
                );
            }
            this.props.close();
        } finally {
            this.state.applying = false;
        }
    }

    onCancel() {
        this.props.close();
    }
}
