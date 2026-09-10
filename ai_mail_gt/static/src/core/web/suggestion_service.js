import { SuggestionService } from "@mail/core/common/suggestion_service";
import { patch } from "@web/core/utils/patch";
import { cleanTerm } from "@mail/utils/common/format";

patch(SuggestionService.prototype, {
    getSupportedDelimiters(thread) {
        let delimiters = super.getSupportedDelimiters(thread);
        if (thread?.model === "discuss.channel" && ['ai_chat', 'channel'].includes(thread?.channel_type)) {
            delimiters.push(['$']);
            if (thread?.channel_type === 'ai_chat') {
                delimiters = delimiters.filter(delimiter => !['@', '#'].includes(delimiter[0]));
            }
        }
        if (thread?.channel_type === 'ai_chat') {
            delimiters.push(['%', 0]);
        }
        return delimiters;
    },

    async fetchSuggestions({ delimiter, term }, { thread } = {}) {
        if (delimiter === '$' && ['ai_chat', 'channel'].includes(thread?.channel_type)) {
            await this.fetchRecordSuggestions(cleanTerm(term), thread);
            return;
        }
        if (delimiter === '%' && thread?.channel_type === 'ai_chat') {
            await this.fetchPromptTemplateSuggestions(cleanTerm(term), thread);
            return;
        }
        return super.fetchSuggestions(...arguments);
    },

    async fetchRecordSuggestions(term, thread) {
        const parts = term.split('/');
        const kwargs = { thread_id: thread.id };

        let suggestions = [];
        if (parts.length === 1) {
            kwargs.term = term;
            suggestions = await this.orm.silent.call(
                "ai.thread",
                "get_model_suggestions",
                [],
                kwargs
            );
            this.store.ModelTagging.insert(suggestions);
        } else if (parts.length === 2) {
            const [model, recordTerm] = parts;
            kwargs.model = model;
            kwargs.record_term = recordTerm || '';
            suggestions = await this.orm.silent.call(
                "ai.thread",
                "get_record_suggestions",
                [],
                kwargs
            );
            this.store.RecordTagging.insert(suggestions);
        }
    },

    async fetchPromptTemplateSuggestions(term, thread) {
        const kwargs = { term: term || '' };
        if (thread?.id) kwargs.channel_id = thread.id;
        const templates = await this.orm.silent.call(
            "ai.prompt.template",
            "get_suggestions",
            [],
            kwargs
        );
        this.store.promptTemplateSuggestions = templates || [];
    },

    searchSuggestions({ delimiter, term }, { thread, sort = false } = {}) {
        if (delimiter === '$' && ['ai_chat', 'channel'].includes(thread?.channel_type)) {
            const parts = cleanTerm(term).split('/', 2);
            let suggestions = [];
            let cleanedTerm = '';
            if (parts.length === 2) {
                cleanedTerm = parts[1].toLowerCase();
                suggestions = Object.values(this.store.RecordTagging.records);
            } else {
                cleanedTerm = parts[0].toLowerCase();
                suggestions = Object.values(this.store.ModelTagging.records);
            }
            const filteredSuggestions = suggestions.filter(suggestion => {
                const name = (suggestion.name || '').toLowerCase();
                const model = (suggestion.model || '').toLowerCase();
                return name.includes(cleanedTerm) || model.includes(cleanedTerm);
            });

            return {
                type: parts.length === 2 ? 'Record' : 'Model',
                suggestions: sort ? filteredSuggestions.slice(0, 8) : filteredSuggestions,
            };
        }
        if (delimiter === '%' && thread?.channel_type === 'ai_chat') {
            return this.searchPromptTemplateSuggestions(cleanTerm(term));
        }
        return super.searchSuggestions(...arguments);
    },

    searchPromptTemplateSuggestions(term) {
        const templates = this.store.promptTemplateSuggestions || [];
        const lterm = term.toLowerCase();
        const filtered = term
            ? templates.filter(t =>
                t.name.toLowerCase().includes(lterm) ||
                t.code.toLowerCase().includes(lterm)
              )
            : templates;
        return {
            type: 'PromptTemplate',
            suggestions: filtered.slice(0, 8),
        };
    },
});
