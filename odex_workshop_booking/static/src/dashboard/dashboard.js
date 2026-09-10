/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PAGE_SIZE = 10;

function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}` +
        `-${String(date.getDate()).padStart(2, "0")}`;
}

export class OdexBookingDashboard extends Component {
    static template = "odex_workshop_booking.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        this.state = useState({
            loading: true,
            data: null,
            year: today.getFullYear(),
            month: today.getMonth(),
            selectedDay: isoDate(today),
            calendarScale: "month",
            companyId: false,
            bookings: [],
            total: 0,
            page: 0,
            search: "",
            stateFilter: false,
            kpiFilter: false,
            detail: null,
            openMenu: null,
        });
        onWillStart(async () => {
            await this.loadDashboard();
            await this.loadBookings();
        });
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------
    async loadDashboard() {
        this.state.loading = true;
        const data = await this.orm.call(
            "odex.workshop.booking", "get_dashboard_data", [], {
                year: this.state.year,
                month: this.state.month + 1,
                day: this.state.selectedDay,
                company_id: this.state.companyId || false,
            });
        this.state.data = data;
        if (!this.state.companyId) {
            this.state.companyId = data.company_id;
        }
        this.state.loading = false;
    }

    async loadBookings() {
        const result = await this.orm.call(
            "odex.workshop.booking", "get_dashboard_bookings", [], {
                offset: this.state.page * PAGE_SIZE,
                limit: PAGE_SIZE,
                search: this.state.search || false,
                state: this.state.stateFilter || false,
                kpi: this.state.kpiFilter || false,
                company_id: this.state.companyId || false,
            });
        this.state.bookings = result.records;
        this.state.total = result.total;
    }

    async refreshAll() {
        await this.loadDashboard();
        await this.loadBookings();
        if (this.state.detail) {
            await this.openDetail(this.state.detail.id);
        }
    }

    // ------------------------------------------------------------------
    // KPIs
    // ------------------------------------------------------------------
    get kpiCards() {
        const k = (this.state.data && this.state.data.kpis) || {};
        return [
            { label: "Total Bookings", value: k.month_total || 0,
              sub: "This Month", icon: "fa-calendar", cls: "owbd-c-purple",
              kpi: "total" },
            { label: "Confirmed", value: k.confirmed || 0,
              sub: (k.confirmed_pct || 0) + "%", icon: "fa-check",
              cls: "owbd-c-green", kpi: "confirmed" },
            { label: "Pending", value: k.pending || 0,
              sub: (k.pending_pct || 0) + "%", icon: "fa-clock-o",
              cls: "owbd-c-orange", kpi: "pending" },
            { label: "Arrived", value: k.arrived || 0,
              sub: (k.arrived_pct || 0) + "%", icon: "fa-sign-in",
              cls: "owbd-c-blue", kpi: "arrived" },
            { label: "Cancelled", value: k.cancelled || 0,
              sub: (k.cancelled_pct || 0) + "%", icon: "fa-times",
              cls: "owbd-c-red", kpi: "cancelled" },
        ];
    }

    async filterByState(state) {
        this.state.stateFilter = this.state.stateFilter === state ? false : state;
        this.state.kpiFilter = false;
        this.state.page = 0;
        await this.loadBookings();
    }

    // Card click: filter the All Bookings table with the SAME domain the
    // server used to produce the number, then scroll to it so the result is
    // visible. Clicking the active card clears the filter.
    async openKpi(kpi) {
        this.state.kpiFilter = this.state.kpiFilter === kpi ? false : kpi;
        this.state.stateFilter = false;
        this.state.page = 0;
        await this.loadBookings();
        const table = document.querySelector(".owbd-bookings-anchor");
        if (table && this.state.kpiFilter) {
            table.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    async openKpiList(kpi) {
        const action = await this.orm.call(
            "odex.workshop.booking", "open_kpi_action", [], {
                kpi: kpi, company_id: this.state.companyId || false,
            });
        this.action.doAction(action);
    }

    // ------------------------------------------------------------------
    // Calendar overview
    // ------------------------------------------------------------------
    get weekdays() {
        return WEEKDAYS;
    }

    get monthLabel() {
        return MONTHS[this.state.month] + " " + this.state.year;
    }

    get calendarCells() {
        const { year, month } = this.state;
        const days = (this.state.data && this.state.data.calendar) || {};
        const cells = [];
        const first = new Date(year, month, 1);
        const offset = (first.getDay() + 6) % 7;
        const prevDays = new Date(year, month, 0).getDate();
        for (let i = offset - 1; i >= 0; i--) {
            cells.push({ label: prevDays - i, muted: true, key: "p" + i });
        }
        const numDays = new Date(year, month + 1, 0).getDate();
        const today = isoDate(new Date());
        for (let d = 1; d <= numDays; d++) {
            const iso = year + "-" + String(month + 1).padStart(2, "0") +
                "-" + String(d).padStart(2, "0");
            cells.push({
                label: d,
                date: iso,
                status: days[iso] || "closed",
                today: iso === today,
                selected: iso === this.state.selectedDay,
                key: iso,
            });
        }
        let tail = 1;
        while (cells.length % 7 !== 0) {
            cells.push({ label: tail, muted: true, key: "n" + tail });
            tail++;
        }
        return cells;
    }

    get visibleCells() {
        const cells = this.calendarCells;
        if (this.state.calendarScale === "month") {
            return cells;
        }
        const index = cells.findIndex((c) => c.date === this.state.selectedDay);
        if (index < 0) {
            return cells.slice(0, 7);
        }
        if (this.state.calendarScale === "week") {
            const start = Math.floor(index / 7) * 7;
            return cells.slice(start, start + 7);
        }
        return [cells[index]];
    }

    setScale(scale) {
        this.state.calendarScale = scale;
    }

    async changeMonth(delta) {
        let month = this.state.month + delta;
        let year = this.state.year;
        if (month < 0) { month = 11; year -= 1; }
        if (month > 11) { month = 0; year += 1; }
        this.state.month = month;
        this.state.year = year;
        await this.loadDashboard();
    }

    async selectDay(cell) {
        if (!cell.date) {
            return;
        }
        this.state.selectedDay = cell.date;
        await this.loadDashboard();
    }

    get selectedDayLabel() {
        const d = new Date(this.state.selectedDay + "T00:00:00");
        return d.toLocaleDateString(undefined,
            { day: "numeric", month: "long", year: "numeric" });
    }

    async onCompanyChange(ev) {
        this.state.companyId = parseInt(ev.target.value) || false;
        this.state.page = 0;
        await this.refreshAll();
    }



    // ------------------------------------------------------------------
    // Slot management panel
    // ------------------------------------------------------------------
    get daySlots() {
        return (this.state.data && this.state.data.day_slots &&
            this.state.data.day_slots.slots) || [];
    }

    get dayTotals() {
        const d = (this.state.data && this.state.data.day_slots) || {};
        return (d.booked || 0) + " / " + (d.capacity || 0);
    }

    toggleMenu(slotId) {
        this.state.openMenu = this.state.openMenu === slotId ? null : slotId;
    }

    async slotAction(slot, action) {
        this.state.openMenu = null;
        try {
            const value = action === "capacity"
                ? window.prompt("New capacity for " + slot.label, slot.capacity)
                : null;
            if (action === "capacity" && !value) {
                return;
            }
            await this.orm.call(
                "odex.booking.slot", "dashboard_slot_action", [], {
                    company_id: this.state.companyId || false,
                    date: slot.date,
                    hour_from: slot.hour_from,
                    action: action,
                    value: value,
                });
            await this.refreshAll();
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) ||
                "The action could not be completed.", { type: "danger" });
        }
    }

    addSlot() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "odex.booking.slot",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_company_id: this.state.companyId,
                default_date: this.state.selectedDay,
            },
        }, { onClose: () => this.loadDashboard() });
    }

    blockTimeSlot() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Block Time Slot",
            res_model: "odex.booking.block.day",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_company_id: this.state.companyId,
                default_date_from: this.state.selectedDay,
                default_date_to: this.state.selectedDay,
            },
        }, { onClose: () => this.refreshAll() });
    }

    // ------------------------------------------------------------------
    // Status donut
    // ------------------------------------------------------------------
    statusColor(state) {
        return {
            draft: "#94a3b8", requested: "#f59e0b", confirmed: "#16a34a",
            arrived: "#2563eb", done: "#475569", cancelled: "#dc2626",
            no_show: "#a855f7",
        }[state] || "#94a3b8";
    }

    _segments(items, radius) {
        const total = items.reduce((sum, i) => sum + i.value, 0);
        if (!total) {
            return [];
        }
        const circumference = 2 * Math.PI * radius;
        let offset = 0;
        return items.map((item) => {
            const length = (item.value / total) * circumference;
            const segment = {
                key: item.key || item.state,
                color: item.color || this.statusColor(item.state),
                dash: length + " " + (circumference - length),
                offset: -offset,
            };
            offset += length;
            return segment;
        });
    }

    get acquisitionSegments() {
        return this._segments(
            (this.state.data && this.state.data.acquisition) || [], 54);
    }

    get acquisitionTotal() {
        return ((this.state.data && this.state.data.acquisition) || [])
            .reduce((sum, i) => sum + i.value, 0);
    }

    async filterByReferral(key) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Bookings",
            res_model: "odex.workshop.booking",
            view_mode: "list,graph,pivot",
            views: [[false, "list"], [false, "graph"], [false, "pivot"]],
            domain: [["referral_source", "=", key === "unknown" ? false : key]],
            target: "current",
        });
    }

    get kpiTitle() {
        const card = this.kpiCards.find((c) => c.kpi === this.state.kpiFilter);
        return card ? card.label : "All Bookings";
    }

    get donutSegments() {
        const items = (this.state.data && this.state.data.status) || [];
        const total = items.reduce((sum, i) => sum + i.value, 0);
        if (!total) {
            return [];
        }
        const circumference = 2 * Math.PI * 54;
        let offset = 0;
        return items.map((item) => {
            const length = (item.value / total) * circumference;
            const segment = {
                key: item.state,
                color: this.statusColor(item.state),
                dash: length + " " + (circumference - length),
                offset: -offset,
            };
            offset += length;
            return segment;
        });
    }

    barPct(item, series) {
        const max = Math.max(1, ...(series || []).map((s) => s.value));
        return Math.round((item.value / max) * 100);
    }

    get canArrive() {
        const state = this.state.detail && this.state.detail.state;
        return state === "confirmed" || state === "requested";
    }

    get canReschedule() {
        const state = this.state.detail && this.state.detail.state;
        return ["draft", "requested", "confirmed", "arrived"].includes(state);
    }

    get canCancel() {
        const state = this.state.detail && this.state.detail.state;
        return !["done", "cancelled", "no_show"].includes(state);
    }

    get donutTotal() {
        return ((this.state.data && this.state.data.status) || [])
            .reduce((sum, i) => sum + i.value, 0);
    }

    // ------------------------------------------------------------------
    // Bookings table
    // ------------------------------------------------------------------
    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.page = 0;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadBookings(), 300);
    }

    get pageLabel() {
        const start = this.state.total ? this.state.page * PAGE_SIZE + 1 : 0;
        const end = Math.min((this.state.page + 1) * PAGE_SIZE, this.state.total);
        return start + "-" + end + " / " + this.state.total;
    }

    async changePage(delta) {
        const next = this.state.page + delta;
        if (next < 0 || next * PAGE_SIZE >= this.state.total) {
            return;
        }
        this.state.page = next;
        await this.loadBookings();
    }

    async openDetail(bookingId) {
        this.state.detail = await this.orm.call(
            "odex.workshop.booking", "get_booking_detail", [],
            { booking_id: bookingId });
    }

    closeDetail() {
        this.state.detail = null;
    }

    async runAction(action) {
        try {
            this.state.detail = await this.orm.call(
                "odex.workshop.booking", "dashboard_action", [], {
                    booking_id: this.state.detail.id, action: action,
                });
            await this.loadDashboard();
            await this.loadBookings();
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) ||
                "The action could not be completed.", { type: "danger" });
        }
    }

    reschedule() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Reschedule Booking",
            res_model: "odex.booking.reschedule",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_booking_id: this.state.detail.id,
                default_old_slot_id: this.state.detail.slot_id || false,
                default_requested_by: "staff",
            },
        }, { onClose: () => this.refreshAll() });
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------
    newBooking() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "odex.workshop.booking",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openBookingForm(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "odex.workshop.booking",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openCalendar() {
        this.action.doAction(
            "odex_workshop_booking.action_workshop_booking_calendar");
    }

    openSlotManagement() {
        this.action.doAction("odex_workshop_booking.action_booking_schedule");
    }
}

registry.category("actions").add("odex_booking_dashboard", OdexBookingDashboard);
