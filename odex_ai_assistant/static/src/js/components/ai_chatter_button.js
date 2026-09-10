/** @odoo-module **/
/**
 * ODEX AI Assistant - Chatter Button Component
 * Injects AI buttons into Odoo's chatter/form views.
 * Uses the action service to open the wizard on any record.
 */

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

export class AiChatterButton extends Component {
    static template = "odex_ai_assistant.AiChatterButton";
    static props = {
        resModel: { type: String, optional: true },
        resId: { type: [Number, Boolean], optional: true },
        resName: { type: String, optional: true },
    };

    setup() {
        this.aiService = useService("odex_ai_service");
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isLoading: false,
            showMenu: false,
        });
    }

    get hasRecord() {
        return this.props.resModel && this.props.resId;
    }

    onToggleMenu() {
        this.state.showMenu = !this.state.showMenu;
    }

    onHideMenu() {
        this.state.showMenu = false;
    }

    async onOpenAIPanel() {
        this.state.showMenu = false;
        this.aiService.setContext(
            this.props.resModel,
            this.props.resId,
            this.props.resName
        );
        this.aiService.openPanel(
            this.props.resModel,
            this.props.resId,
            this.props.resName
        );
    }

    async onOpenWizard() {
        this.state.showMenu = false;
        if (!this.hasRecord) {
            this.notification.add("Please open a record first.", { type: "warning" });
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "odex.ai.chatter.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_res_model: this.props.resModel,
                default_res_id: this.props.resId,
            },
        });
    }

    async onSummarizeToChatter() {
        this.state.showMenu = false;
        if (!this.hasRecord) {
            this.notification.add("Please open a record first.", { type: "warning" });
            return;
        }
        this.state.isLoading = true;
        try {
            await this.aiService.summarizeRecord(
                this.props.resModel,
                this.props.resId,
                true // post to chatter
            );
            this.notification.add("AI summary posted to chatter!", { type: "success" });
        } catch (e) {
            this.notification.add(
                e.message || "Failed to generate summary. Check your API key.",
                { type: "danger" }
            );
        } finally {
            this.state.isLoading = false;
        }
    }
}

// Register the component so it can be used in templates
registry.category("components").add("AiChatterButton", AiChatterButton);
