/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { captureImage } from "./camera";

// Fixed slots, matching the workshop photo sheet. One photo per slot.
const SLOTS = [
    { type: "front", label: _t("Front view") },
    { type: "rear", label: _t("Rear view") },
    { type: "left", label: _t("Left side view") },
    { type: "right", label: _t("Right side view") },
    { type: "top", label: _t("Top view") },
    { type: "front_left", label: _t("Front-left corner") },
    { type: "front_right", label: _t("Front-right corner") },
    { type: "rear_left", label: _t("Rear-left corner") },
    { type: "rear_right", label: _t("Rear-right corner") },
    { type: "damage", label: _t("Any visible dent, scratch, or damage") },
    { type: "odometer", label: _t("Odometer reading") },
    { type: "other", label: _t("Additional photo") },
];

export class PhotoGalleryWidget extends Component {
    static template = "odex_vehicle_gate_pass.PhotoGallery";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            byType: {}, // type -> {id, src, full, caption}
            zoom: null,
            busy: false,
        });
        this.slots = SLOTS;
        this._load();
    }

    get recordId() {
        return this.props.record.resId;
    }

    get filledCount() {
        return Object.keys(this.state.byType).length;
    }

    async _load() {
        if (!this.recordId) {
            this.state.byType = {};
            return;
        }
        const records = await this.orm.searchRead(
            "odex.gate.pass.photo",
            [["gate_pass_id", "=", this.recordId]],
            ["photo_type", "caption", "taken_at"],
            { order: "taken_at desc" }
        );
        const byType = {};
        for (const record of records) {
            if (!byType[record.photo_type]) {
                byType[record.photo_type] = {
                    id: record.id,
                    caption: record.caption || "",
                    src: `/web/image/odex.gate.pass.photo/${record.id}/image_thumb`,
                    full: `/web/image/odex.gate.pass.photo/${record.id}/image`,
                };
            }
        }
        this.state.byType = byType;
    }

    _requireSaved() {
        if (!this.recordId) {
            this.notification.add(_t("Save the gate pass before adding photos."), {
                type: "warning",
            });
            return false;
        }
        return true;
    }

    async onCaptureSlot(slot) {
        if (!this._requireSaved() || this.state.busy) {
            return;
        }
        const image = await captureImage();
        if (!image) {
            return;
        }
        this.state.busy = true;
        try {
            const existing = this.state.byType[slot.type];
            const caption = existing ? existing.caption : "";
            if (existing) {
                await this.orm.unlink("odex.gate.pass.photo", [existing.id]);
            }
            const result = await rpc("/odex_gate_pass/photo/add", {
                gate_pass_id: this.recordId,
                image,
                photo_type: slot.type,
                caption,
            });
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            await this._load();
        } finally {
            this.state.busy = false;
        }
    }

    async onCaptionChange(slot, ev) {
        const entry = this.state.byType[slot.type];
        if (!entry) {
            return;
        }
        entry.caption = ev.target.value;
        await this.orm.write("odex.gate.pass.photo", [entry.id], { caption: entry.caption });
    }

    async onDelete(slot) {
        const entry = this.state.byType[slot.type];
        if (!entry) {
            return;
        }
        await this.orm.unlink("odex.gate.pass.photo", [entry.id]);
        await this._load();
    }

    onZoom(entry) {
        this.state.zoom = entry.full;
    }

    onCloseZoom() {
        this.state.zoom = null;
    }
}

export const photoGalleryWidget = { component: PhotoGalleryWidget };
registry.category("view_widgets").add("odex_photo_gallery", photoGalleryWidget);
