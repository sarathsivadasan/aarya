/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Workshop bay / lift occupancy grid.
 *
 * A bay holds one thing at a time: a job card or a vehicle inspection. The
 * tile shows which, plus that record's number, and opens it on click.
 */
export class BayGrid extends Component {
    static template = "odex_job_card_dashboard.BayGrid";
    static props = {
        bays: Array,
        onOpenJob: Function,
        onViewAll: { type: Function, optional: true },
    };

    stateClass(bay) {
        return `o_jcd_bay o_jcd_bay_${bay.state}`;
    }

    icon(bay) {
        return bay.state === "inspection" ? "fa-search" : "fa-car";
    }

    onBayClick(bay) {
        if (bay.task_id) {
            this.props.onOpenJob(bay.task_id);
        }
    }
}
