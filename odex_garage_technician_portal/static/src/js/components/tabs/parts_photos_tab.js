/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PartsPhotosTab extends Component {
    static template = "odex_garage_technician_portal.PartsPhotosTab";
    static props = { taskId: Number };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            photos: [], uploading: false,
            newPhoto: { part_reference: "", description: "" },
        });
        this.fileInput = useRef("fileInput");
        onWillStart(() => this.loadPhotos());
    }

    async loadPhotos() {
        this.state.photos = await rpc("/technician_portal/parts_photo/list", { task_id: this.props.taskId });
    }

    triggerUpload() {
        this.fileInput.el.click();
    }

    async onFileSelected(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        this.state.uploading = true;
        const dataUrl = await this._compress(file);
        await rpc("/technician_portal/parts_photo/upload", {
            task_id: this.props.taskId, image: dataUrl,
            part_reference: this.state.newPhoto.part_reference,
            description: this.state.newPhoto.description,
        });
        ev.target.value = "";
        this.state.newPhoto = { part_reference: "", description: "" };
        this.state.uploading = false;
        await this.loadPhotos();
    }

    async deletePhoto(id) {
        await rpc("/technician_portal/parts_photo/delete", { photo_id: id });
        await this.loadPhotos();
    }

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
