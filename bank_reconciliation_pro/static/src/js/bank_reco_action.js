/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * BankRecoAction – OWL component that renders the full
 * Tally-style bank reconciliation screen.
 */
class BankRecoAction extends Component {
    static template = "bank_reconciliation_pro.BankRecoAction";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        // ── Reactive State ────────────────────────────────────────
        this.state = useState({
            journals: [],
            partners: [],
            selectedJournal: null,
            recoDate: this._today(),
            lines: [],
            loading: false,
            selectedIds: [],
            searchTerm: "",
            showFilter: "unreconciled",   // unreconciled | all | reconciled
            journalFilter: "all",
            partnerFilter: "all",
            sortField: "date",
            sortDir: "desc",

            // Right panel
            bankDate: this._today(),
            bankReference: "",
            notes: "",

            // Summary
            summary: {
                opening_balance: 0,
                total_debit: 0,
                total_credit: 0,
                cleared_amount: 0,
                pending_amount: 0,
                difference: 0,
                is_mismatch: false,
            },
            openingDateLabel: "",

            // Toast
            toast: null,
        });

        this._toastTimer = null;

        onMounted(async () => {
            await this._loadJournals();
        });

        onWillUnmount(() => {
            if (this._toastTimer) clearTimeout(this._toastTimer);
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // GETTERS
    // ═══════════════════════════════════════════════════════════════

    get allSelected() {
        return (
            this.state.lines.length > 0 &&
            this.state.lines.every((l) => this.state.selectedIds.includes(l.id))
        );
    }

    get selectedTotal() {
        return this.state.lines
            .filter((l) => this.state.selectedIds.includes(l.id))
            .reduce((sum, l) => sum + (l.debit || 0) + (l.credit || 0), 0);
    }

    isSelected(id) {
        return this.state.selectedIds.includes(id);
    }

    rowClass(line) {
        const classes = ["brc-tr"];
        if (this.isSelected(line.id)) classes.push("brc-tr-selected");
        if (line.is_reconciled) classes.push("brc-tr-reconciled");
        return classes.join(" ");
    }

    statusClass(line) {
        return line.status === "reconciled"
            ? "brc-status brc-status-reconciled"
            : "brc-status brc-status-pending";
    }

    sortIcon(field) {
        if (this.state.sortField !== field) return "fa fa-sort brc-sort-icon";
        return this.state.sortDir === "asc"
            ? "fa fa-sort-asc brc-sort-icon brc-sort-active"
            : "fa fa-sort-desc brc-sort-icon brc-sort-active";
    }

    formatAmt(val) {
        if (val === null || val === undefined) return "0.00";
        return Number(val).toLocaleString("en-AE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // LOAD / DATA METHODS
    // ═══════════════════════════════════════════════════════════════

    async _loadJournals() {
        try {
            const journals = await this.orm.call(
                "bank.reco.session",
                "get_journals",
                []
            );
            this.state.journals = journals;
            if (journals.length === 1) {
                this.state.selectedJournal = journals[0].id;
                await this._loadLines();
                await this._loadSummary();
            }
        } catch (e) {
            console.error("Failed to load journals", e);
        }
    }

    async _loadLines() {
        if (!this.state.selectedJournal) return;
        this.state.loading = true;
        try {
            const showReconciled = this.state.showFilter === "all"
                ? true
                : this.state.showFilter === "reconciled";

            let lines = await this.orm.call("bank.reco.session", "get_lines", [
                this.state.selectedJournal,
                this.state.recoDate,
                showReconciled,
                this.state.searchTerm,
                this.state.journalFilter,
                this.state.partnerFilter,
            ]);

            // Client-side filter for "reconciled only"
            if (this.state.showFilter === "reconciled") {
                lines = lines.filter((l) => l.is_reconciled);
            }

            // Client-side sort
            lines = this._sortLines(lines);

            this.state.lines = lines;

            // Build partner list from loaded lines
            const partnerMap = {};
            lines.forEach((l) => {
                if (l.partner) partnerMap[l.partner] = l.partner;
            });
            this.state.partners = Object.keys(partnerMap).map((n, i) => ({
                id: n,
                name: n,
            }));
        } catch (e) {
            console.error("Failed to load lines", e);
        } finally {
            this.state.loading = false;
        }
    }

    async _loadSummary() {
        if (!this.state.selectedJournal) return;
        try {
            const summary = await this.orm.call(
                "bank.reco.session",
                "get_summary",
                [this.state.selectedJournal, this.state.recoDate]
            );
            this.state.summary = summary;
            // Opening date label = day before recoDate
            const d = new Date(this.state.recoDate);
            d.setDate(d.getDate() - 1);
            this.state.openingDateLabel = d.toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
            });
        } catch (e) {
            console.error("Failed to load summary", e);
        }
    }

    _sortLines(lines) {
            const { sortField, sortDir } = this.state;

            return [...lines].sort((a, b) => {
                let va = a[sortField];
                let vb = b[sortField];

                if (sortField === "date") {
                    const [da, ma, ya] = va.split("/");
                    const [db, mb, yb] = vb.split("/");

                    va = new Date(`${ya}-${ma}-${da}`);
                    vb = new Date(`${yb}-${mb}-${db}`);
                }

                if (va < vb) return sortDir === "asc" ? -1 : 1;
                if (va > vb) return sortDir === "asc" ? 1 : -1;
                return 0;
            });
        }

    _today() {
        return new Date().toISOString().split("T")[0];
    }

    // ═══════════════════════════════════════════════════════════════
    // EVENT HANDLERS
    // ═══════════════════════════════════════════════════════════════

    async onJournalChange(ev) {
        this.state.selectedJournal = parseInt(ev.target.value) || null;
        this.state.selectedIds = [];
        await this._loadLines();
        await this._loadSummary();
    }

    async onRecoDateChange(ev) {
        this.state.recoDate = ev.target.value;
        await this._loadLines();
        await this._loadSummary();
    }

    onBankDateChange(ev) {
        this.state.bankDate = ev.target.value;
    }

    onBankRefChange(ev) {
        this.state.bankReference = ev.target.value;
    }

    onNotesChange(ev) {
        this.state.notes = ev.target.value;
    }

    async onShowReconciledChange(ev) {
        this.state.showFilter = ev.target.value;
        this.state.selectedIds = [];
        await this._loadLines();
    }

    async onJournalFilterChange(ev) {
        this.state.journalFilter = ev.target.value;
        await this._loadLines();
    }

    async onPartnerFilterChange(ev) {
        this.state.partnerFilter = ev.target.value;
        await this._loadLines();
    }

    async onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        await this._loadLines();
    }

    onSelectAll(ev) {
        if (ev.target.checked) {
            this.state.selectedIds = this.state.lines
                .filter((l) => !l.is_reconciled)
                .map((l) => l.id);
        } else {
            this.state.selectedIds = [];
        }
    }

    onToggleSelect(id) {
        const idx = this.state.selectedIds.indexOf(id);
        if (idx === -1) {
            this.state.selectedIds = [...this.state.selectedIds, id];
        } else {
            this.state.selectedIds = this.state.selectedIds.filter((i) => i !== id);
        }
    }

    onRowClick(line) {
        if (!line.is_reconciled) {
            this.onToggleSelect(line.id);
        }
    }

    onSort(field) {
        if (this.state.sortField === field) {
            this.state.sortDir = this.state.sortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = field;
            this.state.sortDir = "asc";
        }
        this.state.lines = this._sortLines(this.state.lines);
    }

    // ── Reconciliation Actions ────────────────────────────────────

    async onReconcileSelected() {
        if (this.state.selectedIds.length === 0) return;
        if (!this.state.bankDate) {
            this._showToast("error", "Please set a Bank Date before reconciling.");
            return;
        }
        try {
            await this.orm.call("bank.reco.session", "reconcile_lines", [
                this.state.selectedIds,
                this.state.bankDate,
                this.state.bankReference,
                this.state.notes,
            ]);
            const count = this.state.selectedIds.length;
            this.state.selectedIds = [];
            this.state.bankReference = "";
            this.state.notes = "";
            await this._loadLines();
            await this._loadSummary();
            this._showToast("success", `${count} entr${count > 1 ? "ies" : "y"} reconciled successfully.`);
        } catch (e) {
            this._showToast("error", e.message || "Reconciliation failed.");
        }
    }

    async onQuickReconcile(lineId) {
        if (!this.state.bankDate) {
            this._showToast("error", "Please set a Bank Date first.");
            return;
        }
        try {
            await this.orm.call("bank.reco.session", "reconcile_lines", [
                [lineId],
                this.state.bankDate,
                this.state.bankReference,
                this.state.notes,
            ]);
            await this._loadLines();
            await this._loadSummary();
            this._showToast("success", "Entry reconciled.");
        } catch (e) {
            this._showToast("error", e.message || "Reconciliation failed.");
        }
    }

    async onUnreconcile(lineId) {
        try {
            await this.orm.call("bank.reco.line", "action_unreconcile", [[lineId]]);
            await this._loadLines();
            await this._loadSummary();
            this._showToast("success", "Entry moved back to Pending.");
        } catch (e) {
            this._showToast("error", e.message || "Failed to undo reconciliation.");
        }
    }

    onClearSelection() {
        this.state.selectedIds = [];
    }

    async onFetchTransactions() {
        if (!this.state.selectedJournal) {
            this._showToast("error", "Please select a bank account first.");
            return;
        }
        try {
            const result = await this.orm.call(
                "bank.reco.session",
                "fetch_transactions",
                [this.state.selectedJournal, this.state.recoDate]
            );
            await this._loadLines();
            await this._loadSummary();
            this._showToast(
                "success",
                `Fetched ${result.fetched} new transaction(s) from accounting.`
            );
        } catch (e) {
            this._showToast("error", e.message || "Fetch failed.");
        }
    }

    async onCreateAdjustment() {
        if (!this.state.selectedJournal) {
            this._showToast("error", "Please select a bank account first.");
            return;
        }
        const diff = this.state.summary.difference;
        if (Math.abs(diff) < 0.01) {
            this._showToast("success", "No adjustment needed – books are balanced.");
            return;
        }
        try {
            const result = await this.orm.call(
                "bank.reco.session",
                "create_adjustment_entry",
                [
                    this.state.selectedJournal,
                    diff,
                    this.state.recoDate,
                    "Bank Reconciliation Adjustment",
                ]
            );
            await this._loadLines();
            await this._loadSummary();
            this._showToast("success", `Adjustment entry ${result.name} created.`);
        } catch (e) {
            this._showToast("error", e.message || "Failed to create adjustment.");
        }
    }

    async onReset() {
        this.state.searchTerm = "";
        this.state.showFilter = "unreconciled";
        this.state.journalFilter = "all";
        this.state.partnerFilter = "all";
        this.state.selectedIds = [];
        this.state.bankReference = "";
        this.state.notes = "";
        await this._loadLines();
        await this._loadSummary();
        this._showToast("success", "Filters reset.");
    }

    // ── Toast ─────────────────────────────────────────────────────

    _showToast(type, message) {
        this.state.toast = { type, message };
        if (this._toastTimer) clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            this.state.toast = null;
        }, 3500);
    }
}

// Register as a client action
registry.category("actions").add("bank_reco_pro_action", BankRecoAction);
