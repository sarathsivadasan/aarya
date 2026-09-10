/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart } from "@odoo/owl";

export class NotesTab extends Component {
    static template = "odex_garage_technician_portal.NotesTab";
    static props = { taskId: Number };

    setup() {
        this.state = useState({ notes: [], draft: "" });
        onWillStart(() => this.loadNotes());
    }

    async loadNotes() {
        this.state.notes = await rpc("/technician_portal/note/list", { task_id: this.props.taskId });
    }

    async addNote() {
        if (!this.state.draft.trim()) return;
        await rpc("/technician_portal/note/add", {
            task_id: this.props.taskId, content: `<p>${this.state.draft}</p>`,
        });
        this.state.draft = "";
        await this.loadNotes();
    }
}
