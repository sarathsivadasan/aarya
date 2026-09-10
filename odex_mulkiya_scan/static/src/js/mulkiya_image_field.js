/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, useRef, useState } from "@odoo/owl";

const SUPPORTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_MB = 12;

/**
 * Upload / capture widget for one side of the Mulkiya.
 *
 * Uses a file input with the `capture` attribute rather than getUserMedia: it
 * opens the native camera on phones and tablets, falls back to the file picker
 * on desktop, and needs no HTTPS media permission dance.
 */
export class MulkiyaImageField extends Component {
    static template = "odex_mulkiya_scan.MulkiyaImageField";

    setup() {
        this.notification = useService("notification");
        this.uploadInput = useRef("uploadInput");
        this.cameraInput = useRef("cameraInput");
        this.state = useState({ preview: null, dragOver: false, loading: false });
        this.cacheBust = Date.now();
    }

    get record() {
        return this.props.record;
    }

    get value() {
        return this.record.data[this.props.name];
    }

    get hasImage() {
        return Boolean(this.state.preview || this.value);
    }

    get isReadonly() {
        return Boolean(this.props.readonly);
    }

    get imageSrc() {
        if (this.state.preview) {
            return this.state.preview;
        }
        const value = this.value;
        if (!value) {
            return "";
        }
        if (typeof value === "string" && value.startsWith("data:")) {
            return value;
        }
        if (this.record.resId) {
            const params = new URLSearchParams({
                model: this.record.resModel,
                id: String(this.record.resId),
                field: this.props.name,
                unique: String(this.cacheBust),
            });
            return `/web/image?${params.toString()}`;
        }
        return `data:image/jpeg;base64,${value}`;
    }

    get filenameField() {
        const candidate = this.props.name.replace("image", "filename");
        return candidate in this.record.fields ? candidate : null;
    }

    onUploadClick() {
        this.uploadInput.el && this.uploadInput.el.click();
    }

    onCameraClick() {
        this.cameraInput.el && this.cameraInput.el.click();
    }

    async onFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (file) {
            await this.setFile(file);
        }
    }

    onDragOver(ev) {
        if (this.isReadonly) {
            return;
        }
        ev.preventDefault();
        this.state.dragOver = true;
    }

    onDragLeave() {
        this.state.dragOver = false;
    }

    async onDrop(ev) {
        if (this.isReadonly) {
            return;
        }
        ev.preventDefault();
        this.state.dragOver = false;
        const file = ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) {
            await this.setFile(file);
        }
    }

    async setFile(file) {
        if (!SUPPORTED_TYPES.includes(file.type)) {
            this.notification.add(
                _t("Only JPEG, PNG and WEBP images are supported."),
                { type: "warning" }
            );
            return;
        }
        if (file.size > MAX_MB * 1024 * 1024) {
            this.notification.add(
                _t("This image is larger than %s MB. Please use a smaller picture.", MAX_MB),
                { type: "warning" }
            );
            return;
        }
        this.state.loading = true;
        try {
            const dataUrl = await this.readFile(file);
            this.state.preview = dataUrl;
            const values = { [this.props.name]: dataUrl.split(",")[1] };
            if (this.filenameField) {
                values[this.filenameField] = file.name;
            }
            await this.record.update(values);
        } catch {
            this.notification.add(_t("The image could not be read."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error("unreadable"));
            reader.readAsDataURL(file);
        });
    }

    async onRemove() {
        this.state.preview = null;
        const values = { [this.props.name]: false };
        if (this.filenameField) {
            values[this.filenameField] = false;
        }
        await this.record.update(values);
    }

    onPreview() {
        if (this.imageSrc) {
            window.open(this.imageSrc, "_blank");
        }
    }
}

export const mulkiyaImageField = {
    component: MulkiyaImageField,
    displayName: "Mulkiya Image",
    supportedTypes: ["binary"],
    supportedOptions: [
        { label: "Side", name: "side", type: "string" },
    ],
    extractProps: ({ options }) => ({ side: (options && options.side) || "" }),
};

registry.category("fields").add("mulkiya_image", mulkiyaImageField);
