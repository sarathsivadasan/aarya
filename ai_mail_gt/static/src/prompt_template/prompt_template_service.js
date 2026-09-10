import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

export const promptTemplateService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const caches = reactive({});
        const promises = {};

        function _key({ channelId, assistantId } = {}) {
            if (channelId) return `channel_${channelId}`;
            if (assistantId) return `assistant_${assistantId}`;
            return null;
        }

        function loadTemplates(context = {}) {
            const key = _key(context);
            if (!key) return Promise.resolve();
            if (!promises[key]) {
                const kwargs = { term: "" };
                if (context.channelId) kwargs.channel_id = context.channelId;
                if (context.assistantId) kwargs.assistant_id = context.assistantId;
                promises[key] = orm
                    .call("ai.prompt.template", "get_suggestions", [], kwargs)
                    .then((templates) => { caches[key] = templates || []; return caches[key]; })
                    .catch(() => { delete promises[key]; return []; });
            }
            return promises[key];
        }

        function getTemplates(context = {}) {
            const key = _key(context);
            return key ? (caches[key] || []) : [];
        }

        return { loadTemplates, getTemplates };
    },
};

registry.category("services").add("ai.prompt_template", promptTemplateService);
