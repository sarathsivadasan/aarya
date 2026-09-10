/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/** One horizontal toolbar: period chips, custom range and the entity filters. */
export class FilterBar extends Component {
    static template = "odex_job_card_dashboard.FilterBar";
    static props = {
        filters: Object,
        onChange: Function,
    };

    setup() {
        this.state = useState({ showCustom: this.props.filters.date_filter === "custom" });
        this.periods = [
            { key: "today", label: "Today" },
            { key: "yesterday", label: "Yesterday" },
            { key: "week", label: "This Week" },
            { key: "month", label: "This Month" },
            { key: "all", label: "All Time" },
        ];
    }

    setPeriod(key) {
        this.state.showCustom = false;
        this.props.onChange({ date_filter: key });
    }

    toggleCustom() {
        this.state.showCustom = !this.state.showCustom;
        if (this.state.showCustom) {
            const today = new Date().toISOString().slice(0, 10);
            this.props.onChange({
                date_filter: "custom",
                date_from: this.props.filters.date_from || today,
                date_to: this.props.filters.date_to || today,
            });
        }
    }

    onDate(key, ev) {
        this.props.onChange({ date_filter: "custom", [key]: ev.target.value });
    }

    isActive(key) {
        return this.props.filters.date_filter === key;
    }
}
