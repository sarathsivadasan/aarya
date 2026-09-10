/** @odoo-module **/

/** Format float hours as HH:MM:SS */
export function hoursToHMS(hours) {
    if (!hours || hours < 0) {
        return "00:00:00";
    }
    const totalSeconds = Math.round(hours * 3600);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

/** Format float hours as e.g. "2:30 hr" */
export function hoursToLabel(hours) {
    if (!hours) {
        return "-";
    }
    const h = Math.floor(Math.abs(hours));
    const m = Math.round((Math.abs(hours) - h) * 60);
    return `${h}:${String(m).padStart(2, "0")} hr`;
}

/** Variance label, e.g. "+35 min" / "-10 min" */
export function varianceLabel(hours) {
    if (!hours) {
        return "-";
    }
    const minutes = Math.round(hours * 60);
    return `${minutes > 0 ? "+" : ""}${minutes} min`;
}

/** Server UTC datetime string -> local HH:MM */
export function toLocalTime(dtString) {
    if (!dtString) {
        return "-";
    }
    const dt = new Date(dtString.replace(" ", "T") + "Z");
    return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export const STATUS_META = {
    working: { label: "Working", cls: "status-working" },
    paused: { label: "Paused", cls: "status-paused" },
    completed: { label: "Completed", cls: "status-completed" },
    delayed: { label: "Delayed", cls: "status-delayed" },
    assigned: { label: "Assigned", cls: "status-assigned" },
    idle: { label: "Idle", cls: "status-idle" },
    cancelled: { label: "Cancelled", cls: "status-idle" },
};

export const CHART_COLORS = {
    purple: "#5B4BB7",
    purpleSoft: "#8B7CE0",
    blue: "#2F80ED",
    green: "#27AE60",
    orange: "#F2994A",
    red: "#EB5757",
    grey: "#B0B3C0",
    yellow: "#F2C94C",
};
