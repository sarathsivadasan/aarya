/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class GatePassListController extends ListController {
    /** Open rows in the custom Gate Pass screen instead of the form view. */
    async openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "odex_gatepass_form",
            name: record.data.name || "Gate Pass",
            params: { gate_pass_id: record.resId },
        });
    }

    /** "New" opens a blank custom screen. */
    async createRecord() {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "odex_gatepass_form",
            name: "New Gate Pass",
            params: {},
        });
    }
}

export const gatePassListView = {
    ...listView,
    Controller: GatePassListController,
};

registry.category("views").add("odex_gatepass_list", gatePassListView);
