/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Vehicle Photos tab - reads/writes the real image1..image12 /
 * image{N}_name / image{N}_desc fields directly on project.task
 * (garage_management_odoo). These are the SAME fields shown on the
 * Job Card - no separate photo storage.
 */
export class VehiclePhotosTab extends Component {
    static template = "odex_garage_technician_portal.VehiclePhotosTab";
    static props = { taskId: Number };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ slots: [], uploading: null });
        this.fileInput = useRef("fileInput");
        this._pendingSlot = null;
        onWillStart(() => this.loadSlots());
    }

    async loadSlots() {
        this.state.slots = await rpc("/technician_portal/photo/list", { task_id: this.props.taskId });
    }

    triggerUpload(slot) {
        this._pendingSlot = slot;
        this.fileInput.el.click();
    }

    async onFileSelected(ev) {
        const file = ev.target.files[0];
        const slot = this._pendingSlot;
        if (!file || !slot) return;
        this.state.uploading = slot;
        const dataUrl = await this._compress(file);
        await rpc("/technician_portal/photo/upload", {
            task_id: this.props.taskId, slot, image: dataUrl,
        });
        ev.target.value = "";
        this.state.uploading = null;
        await this.loadSlots();
    }

    async onDescBlur(slot, ev) {
        await rpc("/technician_portal/photo/update_desc", {
            task_id: this.props.taskId, slot: slot.slot, desc: ev.target.value,
        });
    }

    async deletePhoto(slot) {
        await rpc("/technician_portal/photo/delete", { task_id: this.props.taskId, slot });
        await this.loadSlots();
    }

    /** Compress + resize to max 1600px before sending, keeping payloads small. */
    _compress(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const img = new Image();
                img.onload = () => {
                    const maxDim = 1600;
                    let { width, height } = img;
                    if (width > maxDim || height > maxDim) {
                        const ratio = Math.min(maxDim / width, maxDim / height);
                        width = Math.round(width * ratio);
                        height = Math.round(height * ratio);
                    }
                    const canvas = document.createElement("canvas");
                    canvas.width = width;
                    canvas.height = height;
                    canvas.getContext("2d").drawImage(img, 0, 0, width, height);
                    resolve(canvas.toDataURL("image/jpeg", 0.8));
                };
                img.onerror = reject;
                img.src = reader.result;
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
}
