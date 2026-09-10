import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(Composer.prototype, {
    setup() {
        super.setup();
        const applyTemplate = ({ detail: { threadId, text } }) => {
            const thread = this.props.composer.thread
                || this.props.composer.message?.originThread;
            if (thread?.id !== threadId) {
                return;
            }
            this.props.composer.text = text;
            this.props.composer.selection.start = text.length;
            this.props.composer.selection.end = text.length;
            this.props.composer.forceCursorMove = true;
            this.props.composer.autofocus++;
        };
        onMounted(() => this.env.bus.addEventListener('ai_mail_gt.apply_prompt_template', applyTemplate));
        onWillUnmount(() => this.env.bus.removeEventListener('ai_mail_gt.apply_prompt_template', applyTemplate));
    },

    get navigableListProps() {
        const props = super.navigableListProps;
        if (!this.hasSuggestions) {
            return props;
        }
        const suggestions = this.suggestion.state.items.suggestions;
        if (this.suggestion.state.items.type === "Model") {
            return {
                ...props,
                optionTemplate: "ai_mail_gt.Composer.suggestionModel",
                options: suggestions.map((suggestion) => ({
                    label: suggestion.label,
                    name: suggestion.name,
                    record: suggestion,
                    classList: "o-mail-Composer-suggestion",
                })),
            };
        }
        if (this.suggestion.state.items.type === "Record") {
            return {
                ...props,
                optionTemplate: "ai_mail_gt.Composer.suggestionRecord",
                options: suggestions.map((suggestion) => ({
                    label: suggestion.label,
                    name: suggestion.name,
                    record: suggestion,
                    classList: "o-mail-Composer-suggestion",
                })),
            };
        }
        if (this.suggestion.state.items.type === "PromptTemplate") {
            const ptSuggestions = this.suggestion.state.items.suggestions;
            return {
                ...props,
                optionTemplate: "ai_mail_gt.Composer.suggestionPromptTemplate",
                options: ptSuggestions.map((t) => ({
                    label: t.code,
                    name: t.name,
                    record: t,
                    classList: "o-mail-Composer-suggestion",
                })),
            };
        }
        return props;
    },
});
