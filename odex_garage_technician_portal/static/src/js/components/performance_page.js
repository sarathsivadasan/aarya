/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

export class PerformancePage extends Component {
    static template = "odex_garage_technician_portal.PerformancePage";
    static props = {};

    setup() {
        this.state = useState({ data: null });
        onWillStart(async () => {
            this.state.data = await rpc("/technician_portal/performance", {});
        });
    }

    get maxChartHours() {
        if (!this.state.data || !this.state.data.chart) return 1;
        return Math.max(...this.state.data.chart.map((c) => c.hours), 1);
    }

    barHeight(hours) {
        return Math.round((hours / this.maxChartHours) * 100) + "%";
    }
}
