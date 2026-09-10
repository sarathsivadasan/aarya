import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks"
import { onWillStart, onWillUpdateProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
export class AskAI extends Component {
    static template = "ai_mail_gt.ask_ai";
    static components = {
        Dropdown,
        DropdownItem,
    };
    static props = {
        getActiveIds: { type: Function, optional: true },
        resModel: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.store = useService("mail.store");
        this.promptTemplateService = useService("ai.prompt_template");

        this.state = useState({
            assistants: [],
            assistant: {},
            templates: [],
            message: "",
            selectedTemplate: null,
        });
        onWillStart(async () => {
            const assistants = await this.getAssistants(this.props);
            this.state.assistants = assistants;
            this.state.assistant = assistants.length > 0 ? assistants[0] : {};
            if (this.state.assistant.id) {
                this.state.templates = await this.promptTemplateService.loadTemplates({ assistantId: this.state.assistant.id }).catch(() => []);
            }
        });
        onWillUpdateProps(async (nextProps) => {
            this.state.assistants = await this.getAssistants(nextProps);
            this.state.assistant = this.state.assistants.length > 0 ? this.state.assistants[0] : {};
            if (this.state.assistant.id) {
                this.state.templates = await this.promptTemplateService.loadTemplates({ assistantId: this.state.assistant.id }).catch(() => []);
            }
        });
    }

    get activeId() {
        let activeIds = this.props.getActiveIds();
        return activeIds.length > 0 ? activeIds[0] : null;
    }

    get recordTag() {
        if (this.activeId) {
            return `$${this.props.resModel}/${this.activeId}`;
        } else {
            return `$${this.props.resModel}`;
        }
    }

    async getAssistants(props) {
        const assistants = await this.orm.call("ai.assistant", "get_assistants_for_record", [props.resModel, this.activeId]);
        return assistants;
    }

    async onChangeAssistant(ev) {
        const assistant = this.state.assistants.find(assistant => assistant.id === parseInt(ev.target.value));
        this.state.assistant = assistant;
        this.state.selectedTemplate = null;
        this.state.templates = [];
        if (assistant?.id) {
            this.state.templates = await this.promptTemplateService.loadTemplates({ assistantId: assistant.id }).catch(() => []);
        }
    }

    onInputMessage(ev) {
        this.state.message = ev.target.value;
    }

    onKeyDownMessage(ev) {
        if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.onSendMessage(ev);
        }
    }

    onClickTemplate(template) {
        if (this.state.selectedTemplate?.id === template.id) {
            this.state.selectedTemplate = null;
        } else {
            this.state.selectedTemplate = template;
        }
    }

    async onSendMessage(ev) {
        if (!this.state.message && !this.state.selectedTemplate) {
            return;
        }
        const message = this.state.message;
        const templatePrefix = this.state.selectedTemplate ? `%${this.state.selectedTemplate.code} ` : "";
        const fullMessage = `${templatePrefix}${this.recordTag} ${message}`.trim();
        const chat = await this.store.getChat({ partnerId: this.state.assistant.partner_id });
        if (chat) {
            chat.open();
            chat.post(fullMessage);
        }
        this.state.message = "";
        this.state.selectedTemplate = null;
        document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    }
}
export class NavbarAskAI extends AskAI {
    static template = "ai_mail_gt.ask_ai";

    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    get activeId() {
        const controller = this.actionService.currentController;

        return (
            controller?.props?.resId ||
            controller?.props?.record?.resId ||
            null
        );
    }

    async getAssistants() {
        const controller = this.actionService.currentController;

        const model =
            controller?.props?.resModel ||
            controller?.action?.res_model ||
            null;

        const activeId =
            controller?.props?.resId ||
            controller?.props?.record?.resId ||
            null;

        console.log("MODEL:", model);
        console.log("ID:", activeId);
        console.log("CONTROLLER:", controller);

        if (!model) {
            return [];
        }

        return await this.orm.call(
            "ai.assistant",
            "get_assistants_for_record",
            [model, activeId]
        );
    }
}
patch(NavBar, {
    components: {
        ...NavBar.components,
        NavbarAskAI,
    },
});