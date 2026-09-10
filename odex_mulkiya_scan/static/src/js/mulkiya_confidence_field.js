/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

/**
 * Small badge showing the OCR confidence of the field next to it.
 * Anything below the configured threshold is highlighted for verification.
 */
export class MulkiyaConfidenceField extends Component {
    static template = "odex_mulkiya_scan.MulkiyaConfidenceField";

    get value() {
        return this.props.record.data[this.props.name] || 0;
    }

    get threshold() {
        return this.props.record.data.confidence_threshold || 90;
    }

    get isLow() {
        return this.value > 0 && this.value < this.threshold;
    }

    get badgeClass() {
        if (!this.value) {
            return "text-bg-light text-muted";
        }
        return this.isLow ? "text-bg-warning" : "text-bg-success";
    }

    get title() {
        if (!this.value) {
            return "No confidence reported by the OCR provider";
        }
        return this.isLow
            ? `Below the ${this.threshold}% threshold - please verify this value`
            : `OCR confidence: ${this.value}%`;
    }
}

export const mulkiyaConfidenceField = {
    component: MulkiyaConfidenceField,
    displayName: "Mulkiya Confidence",
    supportedTypes: ["integer"],
};

registry.category("fields").add("mulkiya_confidence", mulkiyaConfidenceField);
