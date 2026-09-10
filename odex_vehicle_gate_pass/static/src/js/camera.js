/** @odoo-module **/

/**
 * Camera helper.
 *
 * Opens a modal with a live camera preview when getUserMedia is available, and
 * falls back to a file picker when it is not (unsupported browser or denied
 * permission).  Returns a base64 data URL (without the data: prefix) or null
 * if the user cancels.
 */

function stripPrefix(dataUrl) {
    const comma = dataUrl.indexOf(",");
    return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

function compressImage(source, maxSize = 1600, quality = 0.85) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            let { width, height } = img;
            if (width > maxSize || height > maxSize) {
                const scale = Math.min(maxSize / width, maxSize / height);
                width = Math.round(width * scale);
                height = Math.round(height * scale);
            }
            const canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            canvas.getContext("2d").drawImage(img, 0, 0, width, height);
            resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.onerror = () => resolve(source);
        img.src = source;
    });
}

function pickFile() {
    return new Promise((resolve) => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.capture = "environment";
        input.onchange = () => {
            const file = input.files && input.files[0];
            if (!file) {
                resolve(null);
                return;
            }
            const reader = new FileReader();
            reader.onload = async () => {
                const compressed = await compressImage(reader.result);
                resolve(stripPrefix(compressed));
            };
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(file);
        };
        input.oncancel = () => resolve(null);
        input.click();
    });
}

/**
 * Capture one image. Prefers the live camera, falls back to file upload.
 * @returns {Promise<string|null>} base64 (no prefix) or null on cancel.
 */
export async function captureImage() {
    const hasCamera =
        navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function";
    if (!hasCamera) {
        return pickFile();
    }
    let stream;
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false,
        });
    } catch (error) {
        // Permission denied or no camera: fall back quietly to file upload.
        return pickFile();
    }

    return new Promise((resolve) => {
        const overlay = document.createElement("div");
        overlay.className = "o_gp_camera_overlay";
        overlay.innerHTML = `
            <div class="o_gp_camera_box">
                <video class="o_gp_camera_video" autoplay playsinline></video>
                <canvas class="o_gp_camera_canvas" style="display:none;"></canvas>
                <div class="o_gp_camera_actions">
                    <button class="btn btn-secondary o_gp_cam_cancel">Cancel</button>
                    <button class="btn btn-secondary o_gp_cam_upload">Upload instead</button>
                    <button class="btn btn-primary o_gp_cam_shoot">Capture</button>
                    <button class="btn btn-secondary o_gp_cam_retake" style="display:none;">Retake</button>
                    <button class="btn btn-primary o_gp_cam_use" style="display:none;">Use Photo</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const video = overlay.querySelector(".o_gp_camera_video");
        const canvas = overlay.querySelector(".o_gp_camera_canvas");
        video.srcObject = stream;

        let captured = null;
        const stop = () => {
            stream.getTracks().forEach((track) => track.stop());
            overlay.remove();
        };
        const showLive = () => {
            video.style.display = "block";
            canvas.style.display = "none";
            overlay.querySelector(".o_gp_cam_shoot").style.display = "";
            overlay.querySelector(".o_gp_cam_retake").style.display = "none";
            overlay.querySelector(".o_gp_cam_use").style.display = "none";
        };

        overlay.querySelector(".o_gp_cam_shoot").onclick = () => {
            canvas.width = video.videoWidth || 1280;
            canvas.height = video.videoHeight || 720;
            canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
            captured = canvas.toDataURL("image/jpeg", 0.85);
            video.style.display = "none";
            canvas.style.display = "block";
            overlay.querySelector(".o_gp_cam_shoot").style.display = "none";
            overlay.querySelector(".o_gp_cam_retake").style.display = "";
            overlay.querySelector(".o_gp_cam_use").style.display = "";
        };
        overlay.querySelector(".o_gp_cam_retake").onclick = showLive;
        overlay.querySelector(".o_gp_cam_use").onclick = async () => {
            const compressed = await compressImage(captured);
            stop();
            resolve(stripPrefix(compressed));
        };
        overlay.querySelector(".o_gp_cam_cancel").onclick = () => {
            stop();
            resolve(null);
        };
        overlay.querySelector(".o_gp_cam_upload").onclick = async () => {
            stop();
            resolve(await pickFile());
        };
    });
}
