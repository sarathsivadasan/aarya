/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

export class LogTab extends Component {
    static template = "odex_garage_technician_portal.LogTab";
    static props = { taskId: Number };

    setup() {
        this.state = useState({ logs: [] });
        onWillStart(async () => {
            this.state.logs = await rpc("/technician_portal/log/list", { task_id: this.props.taskId });
        });
    }
}
