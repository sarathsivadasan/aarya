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
import { CHART_COLORS } from "../utils/format";

const REPORTS = [
    { key: "productivity", label: "Technician Productivity" },
    { key: "job_card", label: "Job Card Report" },
    { key: "inspection", label: "Vehicle Inspection Report" },
    { key: "time_analysis", label: "Time Analysis" },
    { key: "attendance", label: "Technician Attendance" },
    { key: "workshop", label: "Daily Workshop Performance" },
];

export class TechnicianOverviewReports extends Component {
    static template = "odex_technician_overview.Reports";
    static props = ["*"];

    setup() {
        this.REPORTS = REPORTS;
        this.state = useState({
            loading: true,
            data: { rows: [], columns: [], trend: {} },
            options: { technicians: [], departments: [], advisors: [] },
            filters: {
                report_type: "productivity",
                period: "month",
                group_by: "day",
                date_from: "",
                date_to: "",
                work_type: "all",
                status: "all",
                technician_id: "",
                department_id: "",
                advisor_id: "",
                search: "",
            },
        });
        this.trendRef = useRef("chartTrend");
        this.stdRef = useRef("chartStd");
        this.charts = {};

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            this.state.options = await rpc("/odex_overview/filter_options");
            await this.load();
        });
        onMounted(() => this.renderCharts());
        onWillUnmount(() =>
            Object.values(this.charts).forEach((c) => c.destroy()));
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await rpc("/odex_overview/report", {
                filters: this.state.filters,
            });
        } finally {
            this.state.loading = false;
        }
        this.renderCharts();
    }

    selectReport(key) {
        this.state.filters.report_type = key;
        this.load();
    }

    onFilterChange() {
        this.load();
    }

    onSearchInput() {
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.load(), 350);
    }

    renderCharts() {
        const trend = this.state.data.trend;
        if (!trend || !window.Chart) {
            return;
        }
        this._chart("trend", this.trendRef, {
            type: "bar",
            data: {
                labels: trend.labels,
                datasets: [
                    {
                        type: "line",
                        label: "Productivity %",
                        data: trend.productivity,
                        borderColor: CHART_COLORS.purple,
                        backgroundColor: CHART_COLORS.purple,
                        yAxisID: "y1",
                        tension: 0.3,
                    },
                    {
                        label: "Total Jobs",
                        data: trend.jobs,
                        backgroundColor: CHART_COLORS.blue,
                        borderRadius: 6,
                    },
                    {
                        label: "Completed",
                        data: trend.completed,
                        backgroundColor: CHART_COLORS.green,
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { position: "bottom" } },
                scales: {
                    y: { beginAtZero: true },
                    y1: {
                        beginAtZero: true,
                        position: "right",
                        grid: { drawOnChartArea: false },
                        max: 150,
                    },
                },
            },
        });
        this._chart("std", this.stdRef, {
            type: "bar",
            data: {
                labels: trend.labels,
                datasets: [
                    {
                        label: "Standard (h)",
                        data: trend.standard,
                        backgroundColor: CHART_COLORS.purpleSoft,
                        borderRadius: 6,
                    },
                    {
                        label: "Actual (h)",
                        data: trend.actual,
                        backgroundColor: CHART_COLORS.orange,
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { position: "bottom" } },
                scales: { y: { beginAtZero: true } },
            },
        });
    }

    _chart(key, ref, config) {
        if (!ref.el) {
            return;
        }
        if (this.charts[key]) {
            this.charts[key].data = config.data;
            this.charts[key].update("none");
            return;
        }
        this.charts[key] = new Chart(ref.el, config);
    }

    exportAs(fmt) {
        const params = encodeURIComponent(JSON.stringify(this.state.filters));
        window.open(`/odex_overview/export/${fmt}?filters=${params}`, "_blank");
    }

    printReport() {
        this.exportAs("pdf");
    }
}

registry.category("actions").add(
    "odex_technician_overview.reports",
    TechnicianOverviewReports
);
