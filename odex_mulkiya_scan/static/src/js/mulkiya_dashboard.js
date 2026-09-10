/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class MulkiyaDashboard extends Component {
    static template = "odex_mulkiya_scan.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            counts: {},
            recent: [],
            states: {},
            canConfigure: false,
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "odex.mulkiya.scan",
                "get_dashboard_data",
                []
            );
            this.state.counts = data.counts || {};
            this.state.recent = data.recent || [];
            this.state.states = data.states || {};
            this.state.canConfigure = Boolean(data.can_configure);
        } finally {
            this.state.loading = false;
        }
    }

    get cards() {
        const counts = this.state.counts;
        return [
            {
                key: "total",
                label: "Total Scans",
                value: counts.total || 0,
                icon: "fa-id-card-o",
                css: "o_mulkiya_card_total",
                domain: [],
            },
            {
                key: "verified",
                label: "Verified",
                value: (counts.verified || 0) + (counts.applied || 0),
                icon: "fa-check-circle",
                css: "o_mulkiya_card_verified",
                domain: [["state", "in", ["verified", "applied"]]],
            },
            {
                key: "extracted",
                label: "To Verify",
                value: counts.extracted || 0,
                icon: "fa-eye",
                css: "o_mulkiya_card_pending",
                domain: [["state", "=", "extracted"]],
            },
            {
                key: "failed",
                label: "Failed",
                value: counts.failed || 0,
                icon: "fa-times-circle",
                css: "o_mulkiya_card_failed",
                domain: [["state", "=", "failed"]],
            },
        ];
    }

    stateLabel(state) {
        return this.state.states[state] || state;
    }

    stateClass(state) {
        switch (state) {
            case "verified":
            case "applied":
                return "text-bg-success";
            case "extracted":
                return "text-bg-warning";
            case "failed":
                return "text-bg-danger";
            case "processing":
            case "uploaded":
                return "text-bg-info";
            default:
                return "text-bg-light text-muted";
        }
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        return String(value).slice(0, 10).split("-").reverse().join("/");
    }

    onNewScan() {
        this.action.doAction("odex_mulkiya_scan.action_mulkiya_scan_new", {
            onClose: () => this.load(),
        });
    }

    onOpenList(domain) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Mulkiya Scans",
                res_model: "odex.mulkiya.scan",
                views: [
                    [false, "list"],
                    [false, "form"],
                ],
                domain: domain || [],
            },
            { onClose: () => this.load() }
        );
    }

    onOpenScan(scanId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "odex.mulkiya.scan",
                res_id: scanId,
                views: [[false, "form"]],
            },
            { onClose: () => this.load() }
        );
    }

    onConfigure() {
        this.action.doAction("odex_mulkiya_scan.action_mulkiya_settings");
    }
}

registry.category("actions").add("odex_mulkiya_dashboard", MulkiyaDashboard);
