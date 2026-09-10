import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AiPromptTemplateCards extends Component {
    static template = "ai_mail_gt.AiPromptTemplateCards";
    static props = {
        thread: Object,
    };

    setup() {
        this.promptTemplateService = useService("ai.prompt_template");
        this.state = useState({ selectedId: null });
        onWillStart(async () => {
            await this.promptTemplateService.loadTemplates({ channelId: this.props.thread.id });
        });
    }

    get templates() {
        return this.promptTemplateService.getTemplates({ channelId: this.props.thread.id });
    }

    onClickTemplate(template) {
        if (this.state.selectedId === template.id) {
            this.state.selectedId = null;
            return;
        }
        this.state.selectedId = template.id;
        this.env.bus.trigger('ai_mail_gt.apply_prompt_template', {
            threadId: this.props.thread.id,
            text: `%${template.code} `,
        });
    }
}
