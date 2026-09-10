/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { loadBundle } from "@web/core/assets";
import {
    Component,
    useState,
    onWillStart,
    onMounted,
    onWillUnmount,
    useRef,
} from "@odoo/owl";
import {
    hoursToHMS,
    hoursToLabel,
    varianceLabel,
    toLocalTime,
    STATUS_META,
    CHART_COLORS,
} from "../utils/format";

const REFRESH_MS = 15000;
const TICK_MS = 1000;

export class TechnicianOverviewDashboard extends Component {
    static template = "odex_technician_overview.Dashboard";
    static props = ["*"];

    setup() {
        this.state = useState({
            loading: true,
            kpis: {},
            rows: [],
            charts: {},
            options: { technicians: [], departments: [], advisors: [] },
            filters: {
                period: "today",
                work_type: "all",
                status: "all",
                technician_id: "",
                department_id: "",
                advisor_id: "",
                search: "",
            },
            serverTime: null,
            now: Date.now(),
            lastSync: null,
        });
        this.chartRefs = {
            productivity: useRef("chartProductivity"),
            status: useRef("chartStatus"),
            stdActual: useRef("chartStdActual"),
            delayed: useRef("chartDelayed"),
            workType: useRef("chartWorkType"),
        };
        this.chartInstances = {};

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            this.state.options = await rpc("/odex_overview/filter_options");
            await this.refresh();
        });
        onMounted(() => {
            this.renderCharts();
            this.pollTimer = setInterval(() => this.refresh(), REFRESH_MS);
            this.tickTimer = setInterval(() => {
                this.state.now = Date.now();
            }, TICK_MS);
        });
        onWillUnmount(() => {
            clearInterval(this.pollTimer);
            clearInterval(this.tickTimer);
            Object.values(this.chartInstances).forEach((c) => c.destroy());
        });
    }

    // ------------------------------------------------------------------
    async refresh() {
        try {
            const data = await rpc("/odex_overview/dashboard", {
                filters: this.state.filters,
            });
            this.state.kpis = data.kpis;
            this.state.rows = data.rows;
            this.state.charts = data.charts;
            this.state.serverTime = data.server_time;
            this.state.serverTimeAt = Date.now();
            this.state.lastSync = new Date().toLocaleTimeString();
            this.state.loading = false;
            this.renderCharts();
        } catch (e) {
            // keep last good data on transient errors
            this.state.loading = false;
        }
    }

    onFilterChange() {
        this.state.loading = true;
        this.refresh();
    }

    /** Department toggle: single active chip, instant refetch, no reload */
    selectDepartment(depId) {
        if (this.state.filters.department_id === depId) {
            return; // no unnecessary queries
        }
        this.state.filters.department_id = depId;
        // reset technician filter if it doesn't belong to the new department
        const tech = this.state.options.technicians.find(
            (t) => String(t.id) === String(this.state.filters.technician_id));
        if (depId && tech && String(tech.department_id) !== String(depId)) {
            this.state.filters.technician_id = "";
        }
        this.onFilterChange();
    }

    isActiveDept(depId) {
        return String(this.state.filters.department_id || "") ===
            String(depId || "");
    }

    /** Technician options limited to the active department (client-side,
     *  no extra RPC) */
    get visibleTechnicians() {
        const depId = this.state.filters.department_id;
        if (!depId) {
            return this.state.options.technicians;
        }
        return this.state.options.technicians.filter(
            (t) => String(t.department_id) === String(depId));
    }

    onSearchInput() {
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.onFilterChange(), 350);
    }

    isLive(row) {
        return !!row.is_ticking;
    }

    remainingHMS(row) {
        if (!row.standard_hours) {
            return "-";
        }
        const remaining = row.standard_hours - this.liveElapsedHours(row);
        return remaining > 0 ? hoursToHMS(remaining) : "00:00:00";
    }

    prodWidth(row) {
        return Math.min(row.productivity || 0, 100);
    }

    // ------------------------------------------------------------------
    // Live elapsed: server value + client drift since last sync
    liveElapsedHours(row) {
        if (!row.is_ticking) {
            return row.elapsed_hours;
        }
        const driftMs = this.state.now - (this.state.serverTimeAt || this.state.now);
        return row.elapsed_hours + Math.max(driftMs, 0) / 3600000;
    }

    elapsedHMS(row) {
        return hoursToHMS(this.liveElapsedHours(row));
    }

    varianceOf(row) {
        if (!row.standard_hours) {
            return { label: "-", exceeded: false };
        }
        const variance = this.liveElapsedHours(row) - row.standard_hours;
        return { label: varianceLabel(variance), exceeded: variance > 0 };
    }

    statusMeta(status) {
        return STATUS_META[status] || STATUS_META.idle;
    }

    fmtHours = hoursToLabel;
    fmtTime = toLocalTime;

    // ------------------------------------------------------------------
    renderCharts() {
        const C = this.state.charts;
        if (!C || !window.Chart) {
            return;
        }
        this._bar("productivity", this.chartRefs.productivity, {
            labels: C.productivity.labels,
            datasets: [{
                label: "Productivity %",
                data: C.productivity.values,
                backgroundColor: C.productivity.types.map((t) =>
                    t === "job_card" ? CHART_COLORS.green : CHART_COLORS.purpleSoft),
                borderRadius: 6,
            }],
        }, { scales: { y: { beginAtZero: true, max: 150 } } });

        this._doughnut("status", this.chartRefs.status, {
            labels: Object.keys(C.status).map(
                (s) => this.statusMeta(s).label),
            datasets: [{
                data: Object.values(C.status),
                backgroundColor: Object.keys(C.status).map((s) => ({
                    working: CHART_COLORS.green,
                    paused: CHART_COLORS.orange,
                    completed: CHART_COLORS.blue,
                    delayed: CHART_COLORS.red,
                    idle: CHART_COLORS.grey,
                }[s] || CHART_COLORS.grey)),
            }],
        }, "pie");

        this._bar("stdActual", this.chartRefs.stdActual, {
            labels: C.std_vs_actual.labels,
            datasets: [
                {
                    label: "Standard (h)",
                    data: C.std_vs_actual.standard,
                    backgroundColor: CHART_COLORS.purpleSoft,
                    borderRadius: 6,
                },
                {
                    label: "Actual (h)",
                    data: C.std_vs_actual.actual,
                    backgroundColor: CHART_COLORS.blue,
                    borderRadius: 6,
                },
            ],
        });

        this._bar("delayed", this.chartRefs.delayed, {
            labels: C.delayed.labels,
            datasets: [{
                label: "Delayed Jobs",
                data: C.delayed.values,
                backgroundColor: CHART_COLORS.red,
                borderRadius: 6,
            }],
        });

        this._doughnut("workType", this.chartRefs.workType, {
            labels: ["Job Card", "Vehicle Inspection"],
            datasets: [{
                data: [C.work_type.job_card, C.work_type.inspection],
                backgroundColor: [CHART_COLORS.yellow, CHART_COLORS.blue],
            }],
        }, "doughnut");
    }

    _bar(key, ref, data, extraOptions = {}) {
        this._chart(key, ref, "bar", data, extraOptions);
    }

    _doughnut(key, ref, data, type = "doughnut") {
        this._chart(key, ref, type, data, {});
    }

    _chart(key, ref, type, data, extraOptions) {
        if (!ref.el) {
            return;
        }
        const existing = this.chartInstances[key];
        if (existing) {
            existing.data = data;
            existing.update("none");
            return;
        }
        this.chartInstances[key] = new Chart(ref.el, {
            type,
            data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { position: "bottom" } },
                ...extraOptions,
            },
        });
    }

    openDocument(row) {
        const resModel = row.task_id ? "project.task" : row.model;
        const resId = row.task_id || row.document_id;
        if (!resId || !resModel) {
            return;
        }
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add(
    "odex_technician_overview.dashboard",
    TechnicianOverviewDashboard
);
