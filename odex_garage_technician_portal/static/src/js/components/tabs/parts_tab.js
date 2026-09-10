/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Parts tab - reads/writes real records directly:
 *   - Vehicle Inspection (isVc=true): vehicle.inspection.part
 *   - Job Card (isVc=false): jobcard.part.requisition
 * Both are the SAME One2many relationships already shown on Vehicle
 * Inspection / Job Card - no separate storage here.
 *
 * v4.0.0 - PART COLUMN
 * The `part` Char field already on vehicle.inspection.part is shown as an
 * editable box. Saving writes the real record, and the server propagates
 * the value to the matching line on the linked Job Card / Vehicle
 * Inspection (updating it, never creating a second line).
 *
 * Rows that come from the linked record and have no counterpart here are
 * listed read-only with an origin badge, so existing part data is visible
 * from both sides without being duplicated into either.
 */
export class PartsTab extends Component {
    static template = "odex_garage_technician_portal.PartsTab";
    static props = { taskId: Number, isVc: { type: Boolean, optional: true } };

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

    get modelName() {
        return this.props.isVc ? "vehicle.inspection.part" : "jobcard.part.requisition";
    }

    async loadLines() {
        this.state.lines = await rpc("/technician_portal/parts/list", { task_id: this.props.taskId });
    }

    get editableLines() {
        return this.state.lines.filter((l) => !l.is_related);
    }

    get relatedLines() {
        return this.state.lines.filter((l) => l.is_related);
    }

    get totalItems() { return this.editableLines.length; }
    get totalQty() { return this.editableLines.reduce((s, l) => s + (l.qty || 0), 0); }

    /** Label under the input when the value shown came from the linked
     *  record rather than from this line. */
    partSourceLabel(line) {
        if (line.part_source === "job_card") { return "from the linked Job Card"; }
        if (line.part_source === "inspection") { return "from the linked Vehicle Inspection"; }
        if (line.part_source === "related") { return "from the linked record"; }
        return "";
    }

    // ---------------- part field ----------------
    /** Debounced so a technician typing doesn't fire an RPC per keystroke;
     *  onPartBlur flushes immediately so nothing is lost on tab-out. */
    onPartInput(line, ev) {
        const value = ev.target.value;
        line.part = value;
        line.part_source = "own";
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
            model: line.model,
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
        this.notification.add(
            this.props.isVc ? "Part added." : "Parts request sent for approval.",
            { type: "success" }
        );
        await this.loadLines();
    }

    async deleteLine(line) {
        const res = await rpc("/technician_portal/parts/delete_line", {
            line_id: line.id, model: line.model,
        });
        if (res.status === "error") {
            this.notification.add(res.message, { type: "danger" });
            return;
        }
        await this.loadLines();
    }
}
