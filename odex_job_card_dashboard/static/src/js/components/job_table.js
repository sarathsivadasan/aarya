/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Generic job card table used by "Today's Job Cards", "Overdue Job Cards"
 * and "Customer Waiting".
 *
 * A column is `{ key, label, type }` where type is one of
 * text | badge | days | muted.
 */
export class JobTable extends Component {
    static template = "odex_job_card_dashboard.JobTable";
    static props = {
        title: String,
        columns: Array,
        rows: Array,
        onRowClick: Function,
        onViewAll: { type: Function, optional: true },
        emptyText: { type: String, optional: true },
        banner: { type: [Object, { value: null }], optional: true },
        rowClass: { type: Function, optional: true },
    };
    static defaultProps = { emptyText: "Nothing to show for this filter." };

    cellValue(row, column) {
        if (column.type === "badge") {
            return (row.stage && row.stage.name) || "";
        }
        return row[column.key] !== undefined && row[column.key] !== null
            ? row[column.key]
            : "";
    }

    badgeStyle(row) {
        const color = (row.stage && row.stage.color) || "#6366F1";
        return `background:${color}1F;color:${color};border:1px solid ${color}40;`;
    }

    lineClass(row) {
        const extra = this.props.rowClass ? this.props.rowClass(row) : "";
        return `o_jcd_row ${extra}`.trim();
    }

    daysClass(row) {
        return `o_jcd_days o_jcd_days_${row.severity || "none"}`;
    }
}
