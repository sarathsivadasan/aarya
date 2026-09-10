/** @odoo-module **/

import { Component } from "@odoo/owl";

/** Shortcut tiles - each one opens a standard Odoo action. */
export class QuickActions extends Component {
    static template = "odex_job_card_dashboard.QuickActions";
    static props = {
        actions: Array,
        onSelect: Function,
    };

    tileStyle(action) {
        return `background:${action.color}14;color:${action.color};`;
    }
}
