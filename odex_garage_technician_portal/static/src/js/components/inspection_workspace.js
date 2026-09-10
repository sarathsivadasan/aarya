/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, onWillUpdateProps, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useNarrowScreen } from "../narrow_screen";

import { ComplaintsTab } from "./tabs/complaints_tab";
import { VehiclePhotosTab } from "./tabs/vehicle_photos_tab";
import { QcTab } from "./tabs/qc_tab";
import { PartsTab } from "./tabs/parts_tab";
import { PartsPhotosTab } from "./tabs/parts_photos_tab";
import { LogTab } from "./tabs/log_tab";
import { NotesTab } from "./tabs/notes_tab";

export class InspectionWorkspace extends Component {
    static template = "odex_garage_technician_portal.InspectionWorkspace";
    static components = { ComplaintsTab, VehiclePhotosTab, QcTab, PartsTab, PartsPhotosTab, LogTab, NotesTab };
    static props = {
        taskType: { type: String, optional: true },
        selectedLineId: { type: [Number, { value: null }], optional: true },
        focusTab: { type: String, optional: true },
        statusFilter: { type: [String, { value: null }], optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.ui = useService("ui");
        // reactive; covers tablet portrait, which ui.isSmall misses
        this.narrow = useNarrowScreen();
        this.state = useState({
            list: [],
            search: "",
            detail: null,
            activeTab: this.props.focusTab || "complaints",
            now: Date.now(), // drives the client-side timer tick
            baseElapsed: 0,   // server-computed elapsed seconds at fetch time
            fetchedAt: Date.now(),
            mobileShowDetail: false,
            bays: [],
            baySupported: false,
            statusFilter: this.props.statusFilter || null,
        });

        onWillStart(async () => {
            await this.loadList();
            if (this.props.selectedLineId) {
                await this.selectLine(this.props.selectedLineId);
            } else if (this.state.list.length && !this.narrow.isNarrow) {
                // on mobile, don't auto-jump into a detail view - let the
                // technician pick from the list first
                await this.selectLine(this.state.list[0].id);
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.statusFilter !== this.props.statusFilter) {
                this.state.statusFilter = nextProps.statusFilter || null;
                this.state.detail = null;
                await this.loadList();
            }
            if (nextProps.selectedLineId && nextProps.selectedLineId !== this.state.detail?.id) {
                await this.selectLine(nextProps.selectedLineId);
            }
        });

        this._ticker = setInterval(() => { this.state.now = Date.now(); }, 1000);
        onWillDestroy(() => clearInterval(this._ticker));
    }

    get isSmall() {
        return this.narrow.isNarrow;
    }

    backToList() {
        this.state.mobileShowDetail = false;
    }

    async loadList() {
        this.state.list = await rpc("/technician_portal/inspection_list", {
            search: this.state.search,
            task_type: this.props.taskType || "is_vc",
            status: this.state.statusFilter || null,
        });
    }

    /** "View All" in the list header - drop the search box and any status
     *  filter arrived at from a Dashboard card, showing every job again. */
    async clearAll() {
        this.state.search = "";
        this.state.statusFilter = null;
        await this.loadList();
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        await this.loadList();
    }

    async selectLine(id) {
        this.state.detail = await rpc("/technician_portal/inspection_detail", { line_id: id });
        // elapsed is computed server-side (against the same timezone
        // convention the data is stored in); we only tick forward locally
        // from the moment we received it.
        this.state.baseElapsed = this.state.detail.elapsed_seconds || 0;
        this.state.fetchedAt = Date.now();
        await this.loadBays();
        if (this.narrow.isNarrow) {
            this.state.mobileShowDetail = true;
        }
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    // ---------------- timer display ----------------
    /** Seconds worked. The SERVER computes this against the same timezone
     *  convention the data is stored in (job_card_extension writes Dubai
     *  wall-clock into UTC fields), so the browser never does that math -
     *  it only ticks forward while the record is actually running. */
    get elapsedSeconds() {
        const d = this.state.detail;
        if (!d) return 0;
        let secs = this.state.baseElapsed || 0;
        if (d.is_ticking) {
            secs += (this.state.now - this.state.fetchedAt) / 1000;
        }
        return Math.max(secs, 0);
    }

    get elapsedDisplay() {
        const secs = this.elapsedSeconds;
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        const s = Math.floor(secs % 60);
        return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    get elapsedHoursDisplay() {
        return (this.elapsedSeconds / 3600).toFixed(2) + " Hours";
    }

    get remainingDisplay() {
        const d = this.state.detail;
        const allocated = (d && d.allocated_hours) || 0;
        const remaining = allocated - this.elapsedSeconds / 3600;
        return Math.max(remaining, 0).toFixed(2) + " Hours";
    }

    get exceededDisplay() {
        const d = this.state.detail;
        const allocated = (d && d.allocated_hours) || 0;
        return Math.max(this.elapsedSeconds / 3600 - allocated, 0).toFixed(2);
    }

    get isExceeded() {
        return parseFloat(this.exceededDisplay) > 0;
    }

    // ---------------- bay (delegates to existing backend) ----------------
    async loadBays() {
        const d = this.state.detail;
        if (!d || !d.bay_supported) {
            this.state.baySupported = false;
            this.state.bays = [];
            return;
        }
        const res = await rpc("/technician_portal/bay/list", { task_id: d.task_id });
        this.state.baySupported = res.supported;
        this.state.bays = res.bays || [];
    }

    async onBaySelected(ev) {
        const bayId = parseInt(ev.target.value, 10);
        if (!bayId) return;
        const res = await rpc("/technician_portal/bay/assign", {
            task_id: this.state.detail.task_id,
            bay_id: bayId,
        });
        if (res.status === "error") {
            // backend validation is the source of truth - show its message
            this.notification.add(res.message, { type: "danger" });
            ev.target.value = this.state.detail.bay_id || "";
            return;
        }
        this.notification.add(`Bay assigned: ${res.bay_name}`, { type: "success" });
        await this.selectLine(this.state.detail.id);
    }

    async releaseBay() {
        const res = await rpc("/technician_portal/bay/release", {
            task_id: this.state.detail.task_id,
        });
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        this.notification.add("Bay released.", { type: "success" });
        await this.selectLine(this.state.detail.id);
    }

    // ---------------- timer actions ----------------
    async start() {
        const res = await rpc("/technician_portal/timer/start", { line_id: this.state.detail.id });
        this._handleResult(res);
    }
    async pause() {
        const res = await rpc("/technician_portal/timer/pause", { line_id: this.state.detail.id });
        this._handleResult(res);
    }
    async resume() {
        const res = await rpc("/technician_portal/timer/resume", { line_id: this.state.detail.id });
        this._handleResult(res);
    }
    async complete() {
        const res = await rpc("/technician_portal/timer/complete", { line_id: this.state.detail.id });
        this._handleResult(res);
    }
    async requestMoreTime() {
        const res = await rpc("/technician_portal/timer/request_more_time", {
            line_id: this.state.detail.id, extra_hours: 0.5, reason: "Time exceeded on job",
        });
        this._handleResult(res, "Notified supervisor for approval.");
    }

    async _handleResult(res, successMsg) {
        if (res && res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        if (successMsg) {
            this.notification.add(successMsg, { type: "success" });
        }
        await this.selectLine(this.state.detail.id);
        await this.loadList();
    }

    print() {
        window.open(`/report/pdf/odex_garage_technician_portal.report_vehicle_inspection/${this.state.detail.task_id}`, "_blank");
    }
}
