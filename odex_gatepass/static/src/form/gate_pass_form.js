/** @odoo-module **/

import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "fleet.gate.pass";
const TIMELINE_FLOW = [
    ["gate_pass_in", "Gate Pass IN"], ["inspection", "Inspection"],
    ["estimate", "Estimation"], ["job_card", "Job Card"],
    ["invoice", "Sales Invoice"], ["gate_pass_out", "Gate Pass OUT"],
];

export class GatePassForm extends Component {
    static template = "odex_gatepass.GatePassForm";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            rec: {},
            logs: [],
            timeline: [],
            ids: [],
            selections: {},
            edit: { customer: false, driver: false, vehicle: false },
            qrOpen: false,
            moreOpen: false,
            logsAll: false,
            noteTab: "internal",
            dirty: false,
            booking: false,
            bookingModel: false,
            bookingOpts: [],
            camera: { open: false, mode: "plate", error: "" },
        });
        this._stream = null;
        this.videoRef = useRef("cameraVideo");
        onWillStart(() => this.load(this.props.action?.params?.gate_pass_id));
    }

    // ------------------------------------------------------------- load/save
    async load(id) {
        this.state.loading = true;
        const p = await this.orm.call(MODEL, "form_load", [id || false]);
        this.state.ids = p.ids;
        this.state.selections = p.selections;
        this.state.rec = p.record || this.blankRecord();
        this.state.logs = p.logs;
        this.state.timeline = p.timeline;
        this.state.booking = p.booking || false;
        this.state.bookingModel = p.booking_model || false;
        this.state.edit = {
            customer: !p.record, driver: !p.record,
            vehicle: !p.record,
        };
        this.state.dirty = false;
        this.state.loading = false;
    }

    blankRecord() {
        return {
            id: false, name: "New", state: "in",
            date_in: luxon.DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
            customer_type: "walkin", job_type: "general_service",
            send_whatsapp_notification: true, send_sms_notification: true,
            inspection_count: 0, job_card_count: 0, estimate_count: 0,
            invoice_count: 0, history_count: 0,
            payment_status: "not_paid", vehicle_status: "in_workshop",
        };
    }

    set(field, value) {
        this.state.rec[field] = value;
        this.state.dirty = true;
    }

    async save(andNew = false) {
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            const r = this.state.rec;
            const vals = {
                date_in: r.date_in, promise_date: r.promise_date || false,
                job_type: r.job_type, customer_type: r.customer_type,
                partner_id: r.partner_id ? r.partner_id.id : false,
                alternate_contact: r.alternate_contact,
                whatsapp_number: r.whatsapp_number,
                driver_name: r.driver_name, driver_license_no: r.driver_license_no,
                driver_license_expiry: r.driver_license_expiry || false,
                driver_mobile: r.driver_mobile,
                vehicle_id: r.vehicle_id ? r.vehicle_id.id : false,
                registration_no: r.registration_no, vin: r.vin,
                engine_no: r.engine_no, variant: r.variant,
                manufacturing_year: r.manufacturing_year,
                fuel_type: r.fuel_type, transmission: r.transmission,
                engine_capacity: r.engine_capacity, plate_source: r.plate_source,
                odometer: r.odometer,
                customer_complaint: r.customer_complaint,
                condition_remarks: r.condition_remarks,
                note: r.note, customer_note: r.customer_note,
                booking_ref: r.booking_ref, out_reason: r.out_reason,
                advisor_id: r.advisor_id ? r.advisor_id.id : false,
                send_whatsapp_notification: r.send_whatsapp_notification,
                send_sms_notification: r.send_sms_notification,
                vehicle_status_override: r.vehicle_status_override || false,
                booking_res_id: r.booking_res_id || false,
            };
            const id = await this.orm.call(MODEL, "form_save", [r.id, vals]);
            this.notification.add(_t("Gate Pass saved"), { type: "success" });
            await this.load(andNew ? false : id);
        } finally {
            this.state.saving = false;
        }
    }

    async cancel() {
        await this.load(this.state.rec.id || false);
    }

    // ------------------------------------------------------------ navigation
    get navIndex() {
        return this.state.ids.indexOf(this.state.rec.id);
    }
    async navMove(delta) {
        const i = this.navIndex + delta;
        if (i >= 0 && i < this.state.ids.length) await this.load(this.state.ids[i]);
    }
    async newRecord() {
        await this.load(false);
    }

    // -------------------------------------------------------------- workflow
    async doOut() {
        if (!this.state.rec.id) return;
        await this.orm.call(MODEL, "vehicle_out", [[this.state.rec.id]]);
        await this.load(this.state.rec.id);
    }
    async doRevisit() {
        if (!this.state.rec.id) return;
        await this.orm.call(MODEL, "vehicle_revisit", [[this.state.rec.id]]);
        await this.load(this.state.rec.id);
    }
    async onStageChange(ev) {
        const v = ev.target.value;
        this.set("vehicle_status_override", v || false);
        if (this.state.rec.id) {
            await this.orm.call(MODEL, "form_save",
                [this.state.rec.id, { vehicle_status_override: v || false }]);
            await this.load(this.state.rec.id);
        }
    }

    // --------------------------------------------------------- smart buttons
    async smart(method) {
        if (!this.state.rec.id) return;
        const act = await this.orm.call(MODEL, method, [[this.state.rec.id]]);
        if (act) this.action.doAction(act);
    }
    openList() {
        this.action.doAction("odex_gatepass.action_gate_pass");
    }

    // --------------------------------------------------------------- utils
    fileToB64(file) {
        return new Promise((res, rej) => {
            const r = new FileReader();
            r.onload = () => res(r.result.split(",")[1]);
            r.onerror = rej;
            r.readAsDataURL(file);
        });
    }

    // -------------------------------------------------------------- lookups
    async searchPartner(ev) {
        await this._m2oSearch(ev, "res.partner", "partner_id");
    }
    async searchVehicle(ev) {
        await this._m2oSearch(ev, "fleet.vehicle", "vehicle_id");
    }
    async _m2oSearch(ev, comodel, field) {
        const term = ev.target.value;
        this.state[field + "_opts"] = term.length > 1
            ? (await this.orm.call(comodel, "name_search", [term], { limit: 8 }))
                .map(([id, name]) => ({ id, name }))
            : [];
    }
    async pickM2o(field, opt) {
        this.set(field, opt);
        this.state[field + "_opts"] = [];
        if (field === "vehicle_id" && opt) {
            const [v] = await this.orm.read("fleet.vehicle", [opt.id],
                ["license_plate", "vin_sn", "driver_id"]);
            this.set("registration_no", v.license_plate || "");
            this.set("vin", v.vin_sn || "");
        }
    }

    // --------------------------------------------------------------- camera
    async openCamera(mode) {
        this.state.camera = { open: true, mode, error: "" };
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" }, audio: false,
            });
            // wait a tick for the <video> to mount
            await new Promise((r) => setTimeout(r, 50));
            if (this.videoRef.el) {
                this.videoRef.el.srcObject = this._stream;
                await this.videoRef.el.play();
            }
        } catch (e) {
            this.state.camera.error = _t(
                "Camera unavailable. Allow camera access or use file upload.");
        }
    }
    closeCamera() {
        if (this._stream) {
            this._stream.getTracks().forEach((t) => t.stop());
            this._stream = null;
        }
        this.state.camera = { open: false, mode: "plate", error: "" };
    }
    async captureFrame() {
        const video = this.videoRef.el;
        if (!video || !video.videoWidth) return;
        const cv = document.createElement("canvas");
        const scale = Math.min(1, 1600 / video.videoWidth); // compress
        cv.width = video.videoWidth * scale;
        cv.height = video.videoHeight * scale;
        cv.getContext("2d").drawImage(video, 0, 0, cv.width, cv.height);
        const b64 = cv.toDataURL("image/jpeg", 0.85).split(",")[1];
        const { mode } = this.state.camera;
        this.closeCamera();
        await this.runScan(b64, mode);
    }
    async runScan(b64, mode) {
        this.notification.add(_t("Scanning..."), { type: "info" });
        const res = await this.orm.call(MODEL, "ocr_scan",
            [b64, mode === "mulkiya" ? "mulkiya" : "plate"]);
        if (res.error) {
            this.notification.add(res.error, { type: "danger" });
            return;
        }
        if (res.registration_no && mode === "plate") {
            this.set("registration_no", res.registration_no);
        }
        if (res.vin) {
            this.set("vin", res.vin);
            const dec = await this.orm.call(MODEL, "vin_decode", [res.vin]);
            if (!dec.error) {
                if (dec.manufacturing_year) this.set("manufacturing_year", dec.manufacturing_year);
                if (dec.engine_capacity) this.set("engine_capacity", dec.engine_capacity + " L");
            }
        }
        if (res.vehicle) {
            // rest of the data comes straight from fleet
            await this.pickM2o("vehicle_id",
                { id: res.vehicle.id, name: res.vehicle.name });
            if (res.vehicle.partner_id) this.set("partner_id", res.vehicle.partner_id);
            this.notification.add(_t("Vehicle found in fleet"), { type: "success" });
        } else {
            this.notification.add(
                _t("Scanned. No matching fleet vehicle — details filled from scan."),
                { type: "warning" });
        }
    }
    async scanUpload(mode, ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file) return;
        const b64 = await this.fileToB64(file);
        await this.runScan(b64, mode);
    }

    // --------------------------------------------------------------- booking
    async bookingSearch(ev) {
        const term = ev.target.value;
        this.set("booking_ref", term);
        if (term.length < 2) { this.state.bookingOpts = []; return; }
        const res = await this.orm.call(MODEL, "booking_search", [term]);
        this.state.bookingOpts = res.results;
    }
    async pickBooking(opt) {
        this.state.bookingOpts = [];
        this.set("booking_res_id", opt.id);
        this.set("booking_ref", opt.name);
        if (this.state.rec.id) {
            await this.orm.call(MODEL, "form_save", [this.state.rec.id, {
                booking_res_id: opt.id, booking_ref: opt.name,
            }]);
            await this.load(this.state.rec.id);
        }
    }
    async openBooking() {
        if (!this.state.rec.id || !this.state.booking) return;
        const act = await this.orm.call(MODEL, "action_open_booking",
            [[this.state.rec.id]]);
        if (act) this.action.doAction(act);
    }

    // -------------------------------------------------------------- helpers
    label(selection, value) {
        const opts = this.state.selections[selection] || [];
        const found = opts.find((o) => o.value === value);
        return found ? found.label : (value || "-");
    }
    fmtDT(v) {
        if (!v) return "-";
        return luxon.DateTime.fromSQL(v, { zone: "utc" }).toLocal()
            .toFormat("dd-LLL-yyyy hh:mm a");
    }
    fmtD(v) {
        if (!v) return "-";
        return luxon.DateTime.fromSQL(v).toFormat("dd-LLL-yyyy");
    }
    get qrUrl() {
        return "/report/barcode/?barcode_type=QR&value=" +
            encodeURIComponent(this.state.rec.name || "") +
            "&width=180&height=180";
    }
    get visibleLogs() {
        return this.state.logsAll ? this.state.logs : this.state.logs.slice(0, 6);
    }
    get timelineRows() {
        return TIMELINE_FLOW.map(([event, title]) => {
            const hit = this.state.timeline.find((t) => t.event === event);
            return {
                event, title,
                date: hit ? this.fmtDT(hit.date) : "",
                by: hit && hit.user_id ? hit.user_id[1] : "",
                done: Boolean(hit),
            };
        });
    }
    print() { window.print(); }
}

registry.category("actions").add("odex_gatepass_form", GatePassForm);
