/** @odoo-module **/
/**
 * ODEX AI Assistant - Navbar Button
 * Adds the AI icon to Odoo's top navigation bar.
 * Uses systray registry to inject into the header.
 */

import { Component, useState, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { AiPanel } from "./ai_panel";

// Systray item: AI button in top navbar
export class AiNavbarButton extends Component {
    static template = "odex_ai_assistant.AiNavbarButton";
    static components = { AiPanel };
    static props = {};

    setup() {
        this.aiService = useService("odex_ai_service");
        this.state = useState({
            isReady: false,
        });

        // Wait for service to initialize
        useEffect(
            () => {
                if (this.aiService.state.isInitialized) {
                    this.state.isReady = true;
                }
            },
            () => [this.aiService.state.isInitialized]
        );
    }

    get aiState() {
        return this.aiService.state;
    }

    get iconClass() {
        return this.aiState.config?.aiIcon || "fa-robot";
    }

    get isActive() {
        return this.aiState.isOpen;
    }

    get hasApiKey() {
        return this.aiState.config?.hasApiKey;
    }

    onTogglePanel() {
        this.aiService.togglePanel();
    }
}

// Register in systray (top-right navbar area)
registry.category("systray").add(
    "odex_ai_assistant.ai_navbar_button",
    {
        Component: AiNavbarButton,
        sequence: 5,
    },
    { force: true }
);
