/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Parts tab - reads/writes jobcard.part.requisition (parts_request)
 * directly: the SAME One2many already shown on the Job Card, no separate
 * storage here.
 *
 * The `part` Char column is an editable box that saves as you type.
 *
 * v5.0.0: the Vehicle Inspection branch (vehicle.inspection.part) and the
 * read-only "linked record" rows were removed with Vehicle Inspection
 * support.
 */
export class PartsTab extends Component {
    static template = "odex_garage_technician_portal.PartsTab";
    static props = { taskId: Number };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            lines: [], products: [],
            newLine: { product_id: null, qty: 1, remarks: "", part: "" },
            saving: {},   // line id -> true while a save is in flight
            saved: {},    // line id -> true briefly after a successful save
        });
        this._partTimers = {};
        onWillStart(async () => {
            await this.loadLines();
            this.state.products = await rpc("/technician_portal/parts/products", {});
        });
    }

    async loadLines() {
        this.state.lines = await rpc("/technician_portal/parts/list", { task_id: this.props.taskId });
    }

    get totalItems() { return this.state.lines.length; }
    get totalQty() { return this.state.lines.reduce((s, l) => s + (l.qty || 0), 0); }

    canDelete(line) {
        return line.state === "draft" || line.state === "reject";
    }

    // ---------------- part field ----------------
    /** Debounced so a technician typing doesn't fire an RPC per keystroke;
     *  onPartBlur flushes immediately so nothing is lost on tab-out. */
    onPartInput(line, ev) {
        const value = ev.target.value;
        line.part = value;
        clearTimeout(this._partTimers[line.id]);
        this._partTimers[line.id] = setTimeout(() => this.savePart(line, value), 700);
    }

    onPartBlur(line, ev) {
        clearTimeout(this._partTimers[line.id]);
        this.savePart(line, ev.target.value);
    }

    onPartKeydown(line, ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.blur();
        }
    }

    async savePart(line, value) {
        if (line._lastSaved === value) {
            return;
        }
        this.state.saving[line.id] = true;
        const res = await rpc("/technician_portal/parts/update_line", {
            line_id: line.id,
            part: value,
        });
        this.state.saving[line.id] = false;
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            await this.loadLines();
            return;
        }
        line._lastSaved = value;
        this.state.saved[line.id] = true;
        setTimeout(() => { this.state.saved[line.id] = false; }, 1500);
    }

    // ---------------- add / delete ----------------
    async addLine() {
        if (!this.state.newLine.product_id) {
            this.notification.add("Choose a product first.", { type: "warning" });
            return;
        }
        const res = await rpc("/technician_portal/parts/add_line", {
            task_id: this.props.taskId,
            product_id: this.state.newLine.product_id,
            qty: this.state.newLine.qty,
            remarks: this.state.newLine.remarks,
            part: this.state.newLine.part,
        });
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        this.state.newLine = { product_id: null, qty: 1, remarks: "", part: "" };
        this.notification.add("Parts request sent for approval.", { type: "success" });
        await this.loadLines();
    }

    async deleteLine(line) {
        const res = await rpc("/technician_portal/parts/delete_line", { line_id: line.id });
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        await this.loadLines();
    }
}
