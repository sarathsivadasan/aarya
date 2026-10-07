/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * One clickable job status tile.
 *
 * Clicking the body opens the filtered job card list; clicking the chevron
 * expands the drill-down panel, which the parent loads on demand.
 */
export class StatusCard extends Component {
    static template = "odex_job_card_dashboard.StatusCard";
    static props = {
        status: Object,
        expanded: { type: Boolean, optional: true },
        details: { type: [Object, { value: null }], optional: true },
        loadingDetails: { type: Boolean, optional: true },
        onOpen: Function,
        onToggle: Function,
        onOpenJob: Function,
        onOpenInspection: Function,
    };

    /** Inline styles keep the tile independent from the asset bundle cache. */
    get tint() {
        const color = this.props.status.color || "#6366F1";
        return `background:${color}1A;border-color:${color}33;`;
    }

    /** Calculated cards (Total Job Card) reuse this tile with one modifier class. */
    get cardClass() {
        return this.props.status.is_special ? "o_jcd_card_special" : "";
    }

    get cardTitle() {
        const status = this.props.status;
        return status.tooltip || `Open all ${status.name} job cards`;
    }

    get iconStyle() {
        return `color:${this.props.status.color || "#6366F1"};`;
    }

    get trendClass() {
        return this.props.status.trend < 0 ? "o_jcd_trend_down" : "o_jcd_trend_up";
    }

    get trendIcon() {
        return this.props.status.trend < 0 ? "fa-caret-down" : "fa-caret-up";
    }

    onCardClick(ev) {
        if (ev.target.closest(".o_jcd_card_toggle, .o_jcd_drill")) {
            return;
        }
        this.props.onOpen(this.props.status);
    }

    onToggleClick(ev) {
        ev.stopPropagation();
        this.props.onToggle(this.props.status);
    }
}
