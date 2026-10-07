/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { BayGrid } from "./components/bay_grid";
import { FilterBar } from "./components/filter_bar";
import { JobTable } from "./components/job_table";
import { QuickActions } from "./components/quick_actions";
import { StatusCard } from "./components/status_card";

const MODEL = "job.card.dashboard";
const BUILD = "1.3.0";

/** Shortcut tiles. Keys are resolved to real actions server side. */
const QUICK_ACTIONS = [
    { key: "new_job_card", label: "New Job Card", icon: "fa-plus-circle", color: "#6366F1" },
    { key: "inspection", label: "Vehicle Inspection", icon: "fa-search", color: "#8B5CF6" },
    { key: "estimate", label: "Estimate", icon: "fa-file-text-o", color: "#EC4899" },
    { key: "invoice", label: "Invoice", icon: "fa-file-o", color: "#0EA5E9" },
    { key: "appointments", label: "Appointments", icon: "fa-calendar", color: "#F59E0B" },
    { key: "technician_board", label: "Technician Board", icon: "fa-users", color: "#EF4444" },
    { key: "reports", label: "Reports", icon: "fa-bar-chart", color: "#10B981" },
    { key: "follow_up", label: "Customer Follow-up", icon: "fa-phone", color: "#3B82F6" },
];

export class JobCardDashboard extends Component {
    static template = "odex_job_card_dashboard.Dashboard";
    static components = { BayGrid, FilterBar, JobTable, QuickActions, StatusCard };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.build = BUILD;
        this.quickActions = QUICK_ACTIONS;
        this.timer = null;

        this.state = useState({
            loading: true,
            refreshing: false,
            error: null,
            data: {},
            filters: { date_filter: "all", date_from: false, date_to: false },
            expanded: null,
            details: {},
            detailsLoading: false,
        });

        onWillStart(async () => {
            await this.load();
            const config = this.state.data.config || {};
            if (config.default_date_filter && !this.userChangedPeriod) {
                this.state.filters.date_filter = config.default_date_filter;
            }
            this.startAutoRefresh();
            this.subscribeToBus();
        });

        onWillUnmount(() => this.stopAutoRefresh());
    }

    // ------------------------------------------------------------------ data
    async load(silent = false) {
        if (silent) {
            this.state.refreshing = true;
        } else {
            this.state.loading = true;
        }
        try {
            const data = await this.orm.call(MODEL, "get_dashboard_data", [
                Object.assign({}, this.state.filters),
            ]);
            this.state.data = data;
            this.state.error = null;
            if (this.state.expanded) {
                await this.loadDetails(this.state.expanded);
            }
        } catch (error) {
            const payload = error && error.data;
            this.state.error =
                (payload && (payload.message || payload.name)) ||
                (error && error.message) ||
                String(error);
        } finally {
            this.state.loading = false;
            this.state.refreshing = false;
        }
    }

    startAutoRefresh() {
        const config = this.state.data.config || {};
        this.stopAutoRefresh();
        if (config.auto_refresh) {
            const interval = Math.max(10, config.refresh_interval || 30) * 1000;
            this.timer = window.setInterval(() => this.load(true), interval);
        }
    }

    stopAutoRefresh() {
        if (this.timer) {
            window.clearInterval(this.timer);
            this.timer = null;
        }
    }

    /** Instant update when a status, technician, promise date or inspection changes. */
    subscribeToBus() {
        try {
            const bus = this.env.services.bus_service;
            if (!bus) {
                return;
            }
            bus.addChannel("job_card_dashboard");
            bus.subscribe("job_card_dashboard/refresh", () => this.load(true));
            bus.start && bus.start();
        } catch {
            // Bus unavailable - the interval refresh keeps the data fresh.
        }
    }

    // --------------------------------------------------------------- filters
    onFilterChange(changes) {
        this.userChangedPeriod = true;
        Object.assign(this.state.filters, changes);
        this.state.expanded = null;
        this.load(true);
    }

    // ------------------------------------------------------------ drill-down
    async doAction(promise) {
        try {
            const action = await promise;
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(
                "This drill-down could not be opened. Check the job card action configuration.",
                { type: "warning" }
            );
            console.warn(error);
        }
    }

    openStatus(status) {
        this.doAction(this.orm.call(MODEL, "get_status_action", [
            status.id, Object.assign({}, this.state.filters),
        ]));
    }

    openJob(taskId) {
        this.doAction(this.orm.call(MODEL, "get_job_card_action", [
            [], "Job Card", taskId,
        ]));
    }

    openOverdue() {
        this.doAction(this.orm.call(MODEL, "get_overdue_action", [
            Object.assign({}, this.state.filters),
        ]));
    }

    openInspection(item) {
        this.doAction(this.orm.call(MODEL, "get_inspection_action", [
            item.key, Object.assign({}, this.state.filters),
        ]));
    }

    openQuickAction(action) {
        this.doAction(this.orm.call(MODEL, "get_quick_action", [action.key]));
    }

    openAlert(alert) {
        this.doAction(this.orm.call(MODEL, "get_job_card_action", [
            alert.domain, alert.label,
        ]));
    }

    openAllJobs() {
        this.doAction(this.orm.call(MODEL, "get_status_action", [
            false, Object.assign({}, this.state.filters),
        ]));
    }

    async toggleStatus(status) {
        if (this.state.expanded === status.id) {
            this.state.expanded = null;
            return;
        }
        this.state.expanded = status.id;
        await this.loadDetails(status.id);
    }

    async loadDetails(stageId) {
        this.state.detailsLoading = true;
        try {
            const details = await this.orm.call(MODEL, "get_stage_details", [
                stageId, Object.assign({}, this.state.filters), 10,
            ]);
            this.state.details = Object.assign({}, this.state.details, {
                [stageId]: details,
            });
        } catch {
            this.state.details = Object.assign({}, this.state.details, {
                [stageId]: { rows: [], inspection: [] },
            });
        } finally {
            this.state.detailsLoading = false;
        }
    }

    // ----------------------------------------------------------------- views
    get widgets() {
        return (this.state.data.config && this.state.data.config.widgets) || {};
    }

    get statuses() {
        return this.state.data.statuses || [];
    }

    get totalJobs() {
        return this.state.data.total || 0;
    }

    get todayColumns() {
        return [
            { key: "number", label: "Job Card", type: "link" },
            { key: "vehicle", label: "Vehicle" },
            { key: "customer", label: "Customer" },
            { key: "advisor", label: "Advisor" },
            { key: "technician", label: "Technician" },
            { key: "promise_date", label: "Promise Date" },
            { key: "stage", label: "Status", type: "badge" },
        ];
    }

    get overdueColumns() {
        return [
            { key: "number", label: "Job Card", type: "link" },
            { key: "vehicle", label: "Vehicle" },
            { key: "customer", label: "Customer" },
            { key: "promise_date", label: "Promise Date" },
            { key: "days_overdue", label: "Days Overdue", type: "days" },
            { key: "stage", label: "Status", type: "badge" },
            { key: "advisor", label: "Advisor" },
            { key: "technician", label: "Technician" },
        ];
    }

    get waitingColumns() {
        return [
            { key: "customer", label: "Customer", type: "link" },
            { key: "vehicle", label: "Vehicle" },
            { key: "waiting_since", label: "Waiting Since" },
            { key: "waiting_time", label: "Waiting Time" },
            { key: "advisor", label: "Advisor" },
            { key: "stage", label: "Current Stage", type: "badge" },
            { key: "status", label: "Status", type: "state" },
        ];
    }

    get overdueBanner() {
        const overdue = this.state.data.overdue || { count: 0 };
        if (!overdue.count) {
            return null;
        }
        return {
            count: overdue.count,
            title: "Jobs Overdue",
            subtitle: "Jobs past their promise date",
        };
    }

    overdueRowClass(row) {
        return `o_jcd_overdue_${row.severity || "none"}`;
    }

}

registry.category("actions").add("odex_job_card_dashboard", JobCardDashboard);
