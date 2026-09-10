/** @odoo-module **/

/**
 * Petty Cash Book - Dashboard JavaScript
 * Odoo 18 Community
 *
 * This module handles the dynamic dashboard rendering
 * by fetching data from the backend controller and
 * populating the HTML dashboard template.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

/**
 * Petty Cash Dashboard Widget
 * Renders full dashboard with live data from backend
 */
class PettyCashDashboardWidget extends Component {
    static template = "petty_cash_book.DashboardWidget";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            data: null,
            dateFrom: this._getFirstDayOfMonth(),
            dateTo: this._getToday(),
            accountId: false,
            journalId: false,
            activeFilter: "this_month",
        });

        onMounted(() => {
            this._loadDashboard();
        });
    }

    _getToday() {
        return new Date().toISOString().split("T")[0];
    }

    _getFirstDayOfMonth() {
        const now = new Date();
        return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
    }

    async _loadDashboard() {
        this.state.loading = true;
        try {
            const result = await this.rpc("/petty_cash/dashboard_data", {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                account_id: this.state.accountId || false,
                journal_id: this.state.journalId || false,
            });
            this.state.data = result;
        } catch (e) {
            this.notification.add("Error loading petty cash data", { type: "danger" });
        }
        this.state.loading = false;
    }

    _formatCurrency(amount, symbol = "AED") {
        return `${symbol} ${parseFloat(amount || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
    }

    async onFilterToday() {
        const today = this._getToday();
        this.state.dateFrom = today;
        this.state.dateTo = today;
        this.state.activeFilter = "today";
        await this._loadDashboard();
    }

    async onFilterThisWeek() {
        const today = new Date();
        const dayOfWeek = today.getDay();
        const start = new Date(today);
        start.setDate(today.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1));
        const end = new Date(start);
        end.setDate(start.getDate() + 6);
        this.state.dateFrom = start.toISOString().split("T")[0];
        this.state.dateTo = end.toISOString().split("T")[0];
        this.state.activeFilter = "this_week";
        await this._loadDashboard();
    }

    async onFilterThisMonth() {
        this.state.dateFrom = this._getFirstDayOfMonth();
        this.state.dateTo = this._getToday();
        this.state.activeFilter = "this_month";
        await this._loadDashboard();
    }

    async onFilterLastMonth() {
        const now = new Date();
        const firstThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        const lastMonthEnd = new Date(firstThisMonth);
        lastMonthEnd.setDate(0);
        const lastMonthStart = new Date(lastMonthEnd.getFullYear(), lastMonthEnd.getMonth(), 1);
        this.state.dateFrom = lastMonthStart.toISOString().split("T")[0];
        this.state.dateTo = lastMonthEnd.toISOString().split("T")[0];
        this.state.activeFilter = "last_month";
        await this._loadDashboard();
    }

    async onFilterThisQuarter() {
        const now = new Date();
        const quarter = Math.floor(now.getMonth() / 3);
        const startMonth = quarter * 3;
        const endMonth = startMonth + 2;
        const start = new Date(now.getFullYear(), startMonth, 1);
        const end = new Date(now.getFullYear(), endMonth + 1, 0);
        this.state.dateFrom = start.toISOString().split("T")[0];
        this.state.dateTo = end.toISOString().split("T")[0];
        this.state.activeFilter = "this_quarter";
        await this._loadDashboard();
    }

    async onFilterThisYear() {
        const now = new Date();
        this.state.dateFrom = `${now.getFullYear()}-01-01`;
        this.state.dateTo = `${now.getFullYear()}-12-31`;
        this.state.activeFilter = "this_year";
        await this._loadDashboard();
    }

    async onApplyFilter() {
        this.state.activeFilter = "custom";
        await this._loadDashboard();
    }

    async onAddReceived() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Add Cash Received",
            res_model: "petty.cash.received",
            view_mode: "form",
            target: "new",
        });
        await this._loadDashboard();
    }

    async onAddExpense() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Add Expense",
            res_model: "petty.cash.expense",
            view_mode: "form",
            target: "new",
        });
        await this._loadDashboard();
    }

    async onEditReceived(id) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "petty.cash.received",
            res_id: id,
            view_mode: "form",
            target: "new",
        });
        await this._loadDashboard();
    }

    async onEditExpense(id) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "petty.cash.expense",
            res_id: id,
            view_mode: "form",
            target: "new",
        });
        await this._loadDashboard();
    }

    async onViewJournalEntries() {
        await this.action.doAction("petty_cash_book.action_petty_cash_received");
    }
}

registry.category("actions").add("petty_cash_book_dashboard", PettyCashDashboardWidget);
