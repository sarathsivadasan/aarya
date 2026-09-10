import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Composer } from "@mail/core/common/composer";
import { ChatWindow } from "@mail/core/common/chat_window";

export class AiTypingIndicator extends Component {
    static template = "ai_mail_gt.AiTypingIndicator";
    static props = { thread: Object };

    setup() {
        this.typing = useState(useService("ai_mail_gt.typing"));
    }

    get isTyping() {
        return !!this.typing.byChannel[this.props.thread.id];
    }

    get statusText() {
        return this.typing.byChannel[this.props.thread.id]?.statusText || "";
    }
}

Composer.components = { ...Composer.components, AiTypingIndicator };
ChatWindow.components = { ...ChatWindow.components, AiTypingIndicator };
