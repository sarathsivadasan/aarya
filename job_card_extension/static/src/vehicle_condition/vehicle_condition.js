/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, useRef, useEffect, onWillStart, onWillUpdateProps } from "@odoo/owl";

const PHOTO_MODEL = "job.card.vehicle.photo";
const DAMAGE_MODEL = "job.card.damage";

/* Same slot sheet as the technician portal (keep in sync with PHOTO_TYPES in python). */
const PHOTO_SLOTS = [
    { key: "front", label: "Front", icon: "fa-car" },
    { key: "rear", label: "Rear", icon: "fa-car" },
    { key: "left", label: "Left Side", icon: "fa-arrow-left" },
    { key: "right", label: "Right Side", icon: "fa-arrow-right" },
    { key: "top", label: "Top View", icon: "fa-arrows-alt" },
    { key: "front_left", label: "Front-Left Corner", icon: "fa-dot-circle-o" },
    { key: "front_right", label: "Front-Right Corner", icon: "fa-dot-circle-o" },
    { key: "rear_left", label: "Rear-Left Corner", icon: "fa-dot-circle-o" },
    { key: "rear_right", label: "Rear-Right Corner", icon: "fa-dot-circle-o" },
    { key: "damage", label: "Any visible dent, scratch, or damage", icon: "fa-exclamation-triangle", multi: true },
    { key: "odometer", label: "Odometer Reading", icon: "fa-tachometer" },
    { key: "additional", label: "Additional Photo", icon: "fa-plus-circle", multi: true },
];

/* Same legend as the gate pass damage map. */
const DAMAGE_TYPES = [
    { key: "dent", code: "D", label: "Dent", color: "#e53935" },
    { key: "scratch", code: "S", label: "Scratch", color: "#fb8c00" },
    { key: "scuff", code: "Sc", label: "Scuff", color: "#fdd835" },
    { key: "crack", code: "C", label: "Crack", color: "#8e24aa" },
    { key: "bent", code: "B", label: "Bent", color: "#3949ab" },
    { key: "paint", code: "P", label: "Paint", color: "#00897b" },
    { key: "missing", code: "M", label: "Missing", color: "#424242" },
    { key: "replaced", code: "R", label: "Replaced", color: "#43a047" },
];
const DAMAGE_BY_KEY = Object.fromEntries(DAMAGE_TYPES.map((d) => [d.key, d]));

/* Gate pass artwork is used when that module is installed so imported
   coordinates land on the same picture; otherwise our own diagram. */
const GATEPASS_MAP = "/odex_vehicle_gate_pass/static/src/img/vehicle/damage_map.jpg";
const OWN_MAP = "/job_card_extension/static/src/img/damage_map.svg";

function m2oName(v) {
    if (!v) return "";
    if (Array.isArray(v)) return v[1] || "";
    return v.display_name || "";
}
function uniq(d) {
    return (d || "").replace(/\D/g, "");
}

async function ensureSaved(record) {
    if (record.isNew || record.dirty) {
        const ok = await record.save();
        if (ok === false) return false;
    }
    return !!record.resId;
}

function readOnlyRecord(props) {
    return !!(props.readonly || props.record.data.is_close);
}

/* ------------------------------------------------------------------ */
/* Image helpers                                                       */
/* ------------------------------------------------------------------ */
function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
    });
}
function canvasToB64(source, w, h, max = 1600) {
    const scale = Math.min(1, max / Math.max(w, h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.85).split(",")[1];
}
async function fileToB64(file) {
    const url = URL.createObjectURL(file);
    try {
        const img = await loadImage(url);
        return canvasToB64(img, img.naturalWidth, img.naturalHeight);
    } finally {
        URL.revokeObjectURL(url);
    }
}

/* ------------------------------------------------------------------ */
/* Vehicle Photos                                                      */
/* ------------------------------------------------------------------ */
export class JcPhotoSheet extends Component {
    static template = "job_card_extension.JcPhotoSheet";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileRef = useRef("file");
        this.videoRef = useRef("video");
        this.slots = PHOTO_SLOTS;
        this.state = useState({
            photos: [],
            loading: false,
            busySlot: null,
            preview: null,
            camera: { open: false, slot: null, replaceId: null, error: "" },
        });
        this.pending = { slot: null, replaceId: null };
        this.stream = null;

        onWillStart(() => this.load(this.props.record.resId));
        onWillUpdateProps((next) => {
            if (next.record.resId !== this.props.record.resId) {
                return this.load(next.record.resId);
            }
        });
        useEffect(
            (open) => {
                if (open) this.startStream();
                return () => this.stopStream();
            },
            () => [this.state.camera.open]
        );
    }

    get readonly() {
        return readOnlyRecord(this.props);
    }
    get takenCount() {
        const keys = new Set(this.state.photos.map((p) => p.photo_type));
        return this.slots.filter((s) => keys.has(s.key)).length;
    }
    get progress() {
        return Math.round((this.takenCount / this.slots.length) * 100);
    }

    async load(resId) {
        if (!resId) {
            this.state.photos = [];
            return;
        }
        this.state.loading = true;
        try {
            this.state.photos = await this.orm.searchRead(
                PHOTO_MODEL,
                [["task_id", "=", resId]],
                ["photo_type", "caption", "write_date", "captured_by", "captured_on"],
                { order: "sequence, id" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    photosOf(key) {
        return this.state.photos.filter((p) => p.photo_type === key);
    }
    thumb(p) {
        return `/web/image/${PHOTO_MODEL}/${p.id}/image_256?unique=${uniq(p.write_date)}`;
    }
    full(p) {
        return `/web/image/${PHOTO_MODEL}/${p.id}/image?unique=${uniq(p.write_date)}`;
    }

    /* --- capture ---------------------------------------------------- */
    async capture(slot, replaceId = null) {
        if (this.readonly) return;
        if (!(await ensureSaved(this.props.record))) return;
        this.pending = { slot: slot.key, replaceId };
        const canCamera = window.isSecureContext && navigator.mediaDevices?.getUserMedia;
        if (canCamera) {
            Object.assign(this.state.camera, { open: true, slot: slot.key, replaceId, error: "" });
        } else {
            this.pickFile(true);
        }
    }
    pickFile(useCapture = false) {
        const input = this.fileRef.el;
        if (!input) return;
        if (useCapture) input.setAttribute("capture", "environment");
        else input.removeAttribute("capture");
        input.value = "";
        input.click();
    }
    async upload(slot, replaceId = null) {
        if (this.readonly) return;
        if (!(await ensureSaved(this.props.record))) return;
        this.pending = { slot: slot.key, replaceId };
        this.pickFile(false);
    }
    async onFileChange(ev) {
        const files = [...(ev.target.files || [])];
        if (!files.length) return;
        const multi = PHOTO_SLOTS.find((s) => s.key === this.pending.slot)?.multi;
        const list = multi ? files : files.slice(0, 1);
        for (const f of list) {
            const b64 = await fileToB64(f);
            await this.savePhoto(b64);
            this.pending.replaceId = null;
        }
    }

    async startStream() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
                audio: false,
            });
            if (this.videoRef.el) {
                this.videoRef.el.srcObject = this.stream;
                await this.videoRef.el.play();
            }
        } catch {
            this.state.camera.error = _t("Camera not available. Use Upload instead.");
        }
    }
    stopStream() {
        if (this.stream) {
            this.stream.getTracks().forEach((t) => t.stop());
            this.stream = null;
        }
    }
    closeCamera() {
        this.state.camera.open = false;
    }
    cameraFallback() {
        this.state.camera.open = false;
        this.pickFile(false);
    }
    async snap() {
        const v = this.videoRef.el;
        if (!v || !v.videoWidth) return;
        const b64 = canvasToB64(v, v.videoWidth, v.videoHeight);
        this.state.camera.open = false;
        await this.savePhoto(b64);
    }

    async savePhoto(b64) {
        const { slot, replaceId } = this.pending;
        const resId = this.props.record.resId;
        this.state.busySlot = slot;
        try {
            const single = !PHOTO_SLOTS.find((s) => s.key === slot)?.multi;
            const existing = replaceId || (single && this.photosOf(slot)[0]?.id);
            if (existing) {
                await this.orm.write(PHOTO_MODEL, [existing], { image: b64 });
            } else {
                await this.orm.create(PHOTO_MODEL, [{ task_id: resId, photo_type: slot, image: b64 }]);
            }
            await this.load(resId);
            this.notification.add(_t("Photo saved"), { type: "success" });
        } catch (e) {
            this.notification.add(e?.data?.message || e?.message || _t("Could not save photo"), { type: "danger" });
        } finally {
            this.state.busySlot = null;
        }
    }

    async saveCaption(p, ev) {
        const caption = ev.target.value || "";
        if (caption === (p.caption || "")) return;
        await this.orm.write(PHOTO_MODEL, [p.id], { caption });
        p.caption = caption;
    }
    async remove(p) {
        if (this.readonly) return;
        if (!window.confirm(_t("Delete this photo?"))) return;
        await this.orm.unlink(PHOTO_MODEL, [p.id]);
        await this.load(this.props.record.resId);
    }
    openPreview(p) {
        this.state.preview = this.full(p);
    }
    closePreview() {
        this.state.preview = null;
    }
}

/* ------------------------------------------------------------------ */
/* Damage Mark                                                         */
/* ------------------------------------------------------------------ */
export class JcDamageMap extends Component {
    static template = "job_card_extension.JcDamageMap";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("map");
        this.types = DAMAGE_TYPES;
        this.state = useState({
            marks: [],
            active: "dent",
            severity: "minor",
            selected: null,
            src: GATEPASS_MAP,
        });
        this.drag = null;
        this.onMove = this.onMove.bind(this);
        this.onUp = this.onUp.bind(this);

        onWillStart(() => this.load(this.props.record.resId));
        onWillUpdateProps((next) => {
            if (next.record.resId !== this.props.record.resId) {
                this.state.selected = null;
                return this.load(next.record.resId);
            }
        });
    }

    get readonly() {
        return readOnlyRecord(this.props);
    }
    get majorCount() {
        return this.state.marks.filter((m) => m.severity === "major").length;
    }
    get summary() {
        return DAMAGE_TYPES.map((t) => ({
            ...t,
            count: this.state.marks.filter((m) => m.damage_type === t.key).length,
        })).filter((t) => t.count);
    }

    async load(resId) {
        if (!resId) {
            this.state.marks = [];
            return;
        }
        this.state.marks = await this.orm.searchRead(
            DAMAGE_MODEL,
            [["task_id", "=", resId]],
            ["damage_type", "severity", "pos_x", "pos_y", "note"],
            { order: "id" }
        );
    }

    onImgError() {
        if (this.state.src !== OWN_MAP) this.state.src = OWN_MAP;
    }

    info(m) {
        return DAMAGE_BY_KEY[m.damage_type] || DAMAGE_TYPES[0];
    }
    markerStyle(m) {
        return `left:${m.pos_x}%;top:${m.pos_y}%;background:${this.info(m).color};`;
    }
    index(m) {
        return this.state.marks.indexOf(m) + 1;
    }

    pointToPct(ev) {
        const r = this.mapRef.el.getBoundingClientRect();
        const clamp = (v) => Math.max(0, Math.min(100, v));
        return {
            x: Math.round(clamp(((ev.clientX - r.left) / r.width) * 100) * 100) / 100,
            y: Math.round(clamp(((ev.clientY - r.top) / r.height) * 100) * 100) / 100,
        };
    }

    async onMapClick(ev) {
        if (this.readonly) return;
        if (!(await ensureSaved(this.props.record))) return;
        const { x, y } = this.pointToPct(ev);
        const vals = {
            task_id: this.props.record.resId,
            damage_type: this.state.active,
            severity: this.state.severity,
            pos_x: x,
            pos_y: y,
        };
        const [id] = await this.orm.create(DAMAGE_MODEL, [vals]);
        const mark = { id, note: "", ...vals };
        this.state.marks.push(mark);
        this.state.selected = null;
    }

    onMarkerDown(ev, m) {
        ev.stopPropagation();
        this.state.selected = m.id;
        if (this.readonly) return;
        this.drag = { mark: m, moved: false, sx: ev.clientX, sy: ev.clientY };
        window.addEventListener("pointermove", this.onMove);
        window.addEventListener("pointerup", this.onUp);
    }
    onMove(ev) {
        if (!this.drag) return;
        if (!this.drag.moved && Math.hypot(ev.clientX - this.drag.sx, ev.clientY - this.drag.sy) < 4) return;
        this.drag.moved = true;
        const { x, y } = this.pointToPct(ev);
        const m = this.state.marks.find((k) => k.id === this.drag.mark.id);
        if (m) {
            m.pos_x = x;
            m.pos_y = y;
        }
    }
    async onUp() {
        window.removeEventListener("pointermove", this.onMove);
        window.removeEventListener("pointerup", this.onUp);
        const d = this.drag;
        this.drag = null;
        if (d && d.moved) {
            const m = this.state.marks.find((k) => k.id === d.mark.id);
            if (m) await this.orm.write(DAMAGE_MODEL, [m.id], { pos_x: m.pos_x, pos_y: m.pos_y });
        }
    }

    noop() {}
    setSeverity(sev) {
        this.state.severity = sev;
    }
    select(m) {
        this.state.selected = m.id;
    }
    selectType(key) {
        this.state.active = key;
    }
    changeType(m, ev) {
        if (!this.readonly && ev.target.value) this.update(m, { damage_type: ev.target.value });
    }
    async update(m, vals) {
        Object.assign(m, vals);
        await this.orm.write(DAMAGE_MODEL, [m.id], vals);
    }
    toggleSeverity(m) {
        if (this.readonly) return;
        this.update(m, { severity: m.severity === "major" ? "minor" : "major" });
    }
    saveNote(m, ev) {
        const note = ev.target.value || "";
        if (note !== (m.note || "")) this.update(m, { note });
    }
    async remove(m) {
        if (this.readonly) return;
        await this.orm.unlink(DAMAGE_MODEL, [m.id]);
        this.state.marks = this.state.marks.filter((k) => k.id !== m.id);
        if (this.state.selected === m.id) this.state.selected = null;
    }
    async clearAll() {
        if (this.readonly || !this.state.marks.length) return;
        if (!window.confirm(_t("Remove all damage marks?"))) return;
        await this.orm.unlink(DAMAGE_MODEL, this.state.marks.map((m) => m.id));
        this.state.marks = [];
        this.state.selected = null;
    }
}

/* ------------------------------------------------------------------ */
/* Header summary card                                                 */
/* ------------------------------------------------------------------ */
export class JcHeroCard extends Component {
    static template = "job_card_extension.JcHeroCard";

    get d() {
        return this.props.record.data;
    }
    get plate() {
        return m2oName(this.d.vehicle_id) || _t("No vehicle");
    }
    get vehicleLine() {
        return [m2oName(this.d.brand), m2oName(this.d.model_id), this.d.year].filter(Boolean).join(" · ");
    }
    get customer() {
        return m2oName(this.d.partner_id);
    }
    get stage() {
        return m2oName(this.d.cc_stage_id);
    }
    get bay() {
        return m2oName(this.d.bay_id);
    }
    get promise() {
        const p = this.d.promise_date;
        return p && p.toFormat ? p.toFormat("dd MMM yyyy") : "";
    }
    get overdue() {
        const p = this.d.promise_date;
        if (!p || !p.toJSDate || this.d.is_close) return false;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return p.toJSDate() < today;
    }
    get fuel() {
        const v = this.d.fuel_level;
        if (v === undefined || v === false || v === null || v === "") return "";
        const sel = this.props.record.fields.fuel_level?.selection;
        if (sel) {
            const hit = sel.find((s) => s[0] === v);
            return hit ? hit[1] : String(v);
        }
        return String(v);
    }
}

const viewWidgets = registry.category("view_widgets");
viewWidgets.add("jc_photo_sheet", { component: JcPhotoSheet });
viewWidgets.add("jc_damage_map", { component: JcDamageMap });
viewWidgets.add("jc_hero_card", { component: JcHeroCard });
