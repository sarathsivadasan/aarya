/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

export class QcTab extends Component {
    static template = "odex_garage_technician_portal.QcTab";
    static props = { taskId: Number };

    setup() {
        this.state = useState({ lines: [] });
        onWillStart(() => this.loadLines());
    }

    async loadLines() {
        this.state.lines = await rpc("/technician_portal/qc/list", { task_id: this.props.taskId });
    }

    async toggleCheck(line) {
        await rpc("/technician_portal/qc/update", { line_id: line.id, check_mark: !line.check_mark });
        await this.loadLines();
    }

    async onDescriptionBlur(line, ev) {
        await rpc("/technician_portal/qc/update", { line_id: line.id, description: ev.target.value });
    }
}
