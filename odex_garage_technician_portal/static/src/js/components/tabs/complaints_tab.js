/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

/**
 * Complaints tab - READ ONLY view of job.requested.service
 * (requested_services_ids on project.task), the SAME records shown on
 * Vehicle Inspection / Job Card.
 *
 * Service, Instruction and Assign Hours are all maintained upstream on
 * the Job Card / Vehicle Inspection form - the technician only reads
 * them here. Assign Hours and the assignee list come from the linked
 * timesheet lines (job_card_daily_report_ids), matched per service.
 */
export class ComplaintsTab extends Component {
    static template = "odex_garage_technician_portal.ComplaintsTab";
    static props = { taskId: Number };

    setup() {
        this.state = useState({ lines: [] });
        onWillStart(() => this.loadLines());
    }

    async loadLines() {
        this.state.lines = await rpc("/technician_portal/complaints/list", { task_id: this.props.taskId });
    }
}
