/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Legend, matching the artwork and the Python model.
const LEGEND = [
    { key: "dent", code: "D", label: _t("Dent"), color: "#dc2626" },
    { key: "scratch", code: "S", label: _t("Scratch"), color: "#2563eb" },
    { key: "scuff", code: "Sc", label: _t("Scuff"), color: "#16a34a" },
    { key: "crack", code: "C", label: _t("Crack"), color: "#f59e0b" },
    { key: "bent", code: "B", label: _t("Bent"), color: "#7c3aed" },
    { key: "paint", code: "P", label: _t("Paint Damage"), color: "#b45309" },
    { key: "missing", code: "M", label: _t("Missing"), color: "#eab308" },
    { key: "replaced", code: "R", label: _t("Replaced"), color: "#111827" },
];
const SEVERITIES = [
    { key: "minor", label: _t("Minor") },
    { key: "major", label: _t("Major") },
];

export class DamageMapWidget extends Component {
    static template = "odex_vehicle_gate_pass.DamageMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.diagram = useRef("diagram");
        this.state = useState({
            damageType: "dent",
            severity: "minor",
            selectedId: null,
            markers: [],
        });
        this.legend = LEGEND;
        this.severities = SEVERITIES;
        this._loadMarkers();
    }

    get recordId() {
        return this.props.record.resId;
    }

    get imageSrc() {
        return "/odex_vehicle_gate_pass/static/src/img/vehicle/damage_map.jpg";
    }

    meta(key) {
        return LEGEND.find((item) => item.key === key) || LEGEND[0];
    }

    async _loadMarkers() {
        if (!this.recordId) {
            this.state.markers = [];
            return;
        }
        const records = await this.orm.searchRead(
            "odex.gate.pass.damage",
            [["gate_pass_id", "=", this.recordId]],
            ["damage_type", "severity", "x_position", "y_position", "description"]
        );
        this.state.markers = records.map((record) => ({
            id: record.id,
            damage_type: record.damage_type,
            severity: record.severity,
            x: record.x_position,
            y: record.y_position,
            description: record.description || "",
        }));
    }

    async onDiagramClick(ev) {
        if (!this.recordId) {
            this.notification.add(_t("Save the gate pass before marking damage."), {
                type: "warning",
            });
            return;
        }
        if (ev.target.classList.contains("o_gp_marker")) {
            return;
        }
        const rect = this.diagram.el.getBoundingClientRect();
        const x = Math.max(0, Math.min(100, ((ev.clientX - rect.left) / rect.width) * 100));
        const y = Math.max(0, Math.min(100, ((ev.clientY - rect.top) / rect.height) * 100));
        const id = await this.orm.create("odex.gate.pass.damage", [
            {
                gate_pass_id: this.recordId,
                view: "map",
                damage_type: this.state.damageType,
                severity: this.state.severity,
                x_position: x,
                y_position: y,
            },
        ]);
        this.state.markers.push({
            id: id[0],
            damage_type: this.state.damageType,
            severity: this.state.severity,
            x,
            y,
            description: "",
        });
        this.state.selectedId = id[0];
    }

    onMarkerPointerDown(marker, ev) {
        ev.stopPropagation();
        this.state.selectedId = marker.id;
        const rect = this.diagram.el.getBoundingClientRect();
        const move = (moveEv) => {
            marker.x = Math.max(0, Math.min(100, ((moveEv.clientX - rect.left) / rect.width) * 100));
            marker.y = Math.max(0, Math.min(100, ((moveEv.clientY - rect.top) / rect.height) * 100));
        };
        const up = async () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            await this.orm.write("odex.gate.pass.damage", [marker.id], {
                x_position: marker.x,
                y_position: marker.y,
            });
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
    }

    async onTypeChange(marker, ev) {
        marker.damage_type = ev.target.value;
        await this.orm.write("odex.gate.pass.damage", [marker.id], {
            damage_type: marker.damage_type,
        });
    }

    async onSeverityChange(marker, ev) {
        marker.severity = ev.target.value;
        await this.orm.write("odex.gate.pass.damage", [marker.id], { severity: marker.severity });
    }

    async onNoteChange(marker, ev) {
        marker.description = ev.target.value;
        await this.orm.write("odex.gate.pass.damage", [marker.id], {
            description: marker.description,
        });
    }

    async onDelete(marker) {
        await this.orm.unlink("odex.gate.pass.damage", [marker.id]);
        this.state.markers = this.state.markers.filter((item) => item.id !== marker.id);
        if (this.state.selectedId === marker.id) {
            this.state.selectedId = null;
        }
    }

    get selectedMarker() {
        return this.state.markers.find((marker) => marker.id === this.state.selectedId) || null;
    }
}

export const damageMapWidget = { component: DamageMapWidget };
registry.category("view_widgets").add("odex_damage_map", damageMapWidget);
