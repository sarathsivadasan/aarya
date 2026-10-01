/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";

export class DashboardPage extends Component {
    static template = "odex_garage_technician_portal.DashboardPage";
    static props = {
        openJob: { type: Function, optional: true },
        viewAll: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            counters: { assigned: 0, in_progress: 0, paused: 0, completed_today: 0, hours_today: 0 },
            recent: [],
        });

        onWillStart(async () => {
            await this.loadCounters();
            this.state.recent = await rpc("/technician_portal/job_list", {});
        });

        // live refresh every 30s, same pattern the reference "Realtime counters" spec asks for
        this._interval = setInterval(() => this.loadCounters(), 30000);
        onWillDestroy(() => clearInterval(this._interval));
    }

    async loadCounters() {
        this.state.counters = await rpc("/technician_portal/dashboard_counters", {});
    }

    /** id is an account.analytic.line id - the portal's primary record. */
    openTask(id) {
        if (this.props.openJob) {
            this.props.openJob(id);
        }
    }

    /** status: not_started | running | paused | completed | null (all)
     *  page: 'job_card' | 'performance' */
    viewAll(status, page = "job_card") {
        if (this.props.viewAll) {
            this.props.viewAll(status, page);
        }
    }
}
