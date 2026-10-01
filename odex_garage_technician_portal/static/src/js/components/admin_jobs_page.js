/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Administrator view - every assigned job in the workshop (requirement 3).
 *
 * The list is built from account.analytic.line on Job Cards, which is
 * where a technician assignment actually lives.
 *
 * Pause / Resume / Stop hit the admin routes, which call the same
 * _do_pause() / _do_resume() / _do_end() internals the technician's own
 * buttons call. Status and time tracking therefore move identically; only
 * the log entry differs, and it records both the technician and the
 * administrator who acted.
 */
export class AdminJobsPage extends Component {
    static template = "odex_garage_technician_portal.AdminJobsPage";
    static props = {};

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            counters: { assigned: 0, in_progress: 0, paused: 0, completed_today: 0, technicians_active: 0 },
            jobs: [],
            technicians: [],
            logs: [],
            filters: { search: "", status: "", technician_id: "" },
            selectedJobId: null,
            busy: {},
            loading: true,
        });

        onWillStart(async () => {
            await Promise.all([this.loadJobs(), this.loadCounters(), this.loadTechnicians()]);
            await this.loadLogs();
            this.state.loading = false;
        });

        // keep the board live without hammering the server
        this._interval = setInterval(() => {
            this.loadCounters();
            this.loadJobs();
        }, 30000);
        onWillDestroy(() => clearInterval(this._interval));
    }

    async loadCounters() {
        this.state.counters = await rpc("/technician_portal/admin/counters", {});
    }

    async loadTechnicians() {
        this.state.technicians = await rpc("/technician_portal/admin/technicians", {});
    }

    async loadJobs() {
        const f = this.state.filters;
        this.state.jobs = await rpc("/technician_portal/admin/jobs", {
            search: f.search || "",
            status: f.status || null,
            technician_id: f.technician_id ? parseInt(f.technician_id, 10) : null,
        });
    }

    async loadLogs() {
        this.state.logs = await rpc("/technician_portal/admin/logs", {
            line_id: this.state.selectedJobId || null,
            limit: 100,
        });
    }

    async onFilterChange() {
        await this.loadJobs();
    }

    async onSearchInput(ev) {
        this.state.filters.search = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadJobs(), 350);
    }

    async clearFilters() {
        this.state.filters = { search: "", status: "", technician_id: "" };
        await this.loadJobs();
    }

    /** Click a row to narrow the activity log to that job. Click again to
     *  go back to the full workshop log. */
    async selectJob(job) {
        this.state.selectedJobId = this.state.selectedJobId === job.id ? null : job.id;
        await this.loadLogs();
    }

    get selectedJobLabel() {
        const job = this.state.jobs.find((j) => j.id === this.state.selectedJobId);
        return job ? `${job.task_name} - ${job.technician}` : "";
    }

    statusLabel(status) {
        return {
            not_started: "Not Started",
            running: "Running",
            paused: "Paused",
            completed: "Completed",
        }[status] || status;
    }

    logDisplay(iso) {
        if (!iso) { return "-"; }
        // Timestamps come from the same source convention the timer writes
        // in, so render them literally rather than re-shifting the zone.
        return iso.replace("T", " ").slice(0, 16);
    }

    // ---------------- administrator actions ----------------
    async _act(job, route, successMsg) {
        this.state.busy[job.id] = true;
        const res = await rpc(route, { line_id: job.id });
        this.state.busy[job.id] = false;
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        this.notification.add(successMsg, { type: "success" });
        await Promise.all([this.loadJobs(), this.loadCounters(), this.loadLogs()]);
    }

    startJob(job) {
        return this._act(job, "/technician_portal/admin/timer/start",
            `Started ${job.task_name} for ${job.technician}.`);
    }

    pauseJob(job) {
        return this._act(job, "/technician_portal/admin/timer/pause",
            `Paused ${job.task_name}.`);
    }

    resumeJob(job) {
        return this._act(job, "/technician_portal/admin/timer/resume",
            `Resumed ${job.task_name}.`);
    }

    stopJob(job) {
        return this._act(job, "/technician_portal/admin/timer/stop",
            `Stopped ${job.task_name}.`);
    }
}
