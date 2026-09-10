import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

registry.category("services").add("ai_mail_gt.typing", {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        const state = reactive({ byChannel: {} });

        bus_service.subscribe("ai_mail_gt/ai_typing_status", ({ channel_id, is_typing, status_text }) => {
            if (is_typing) {
                clearTimeout(state.byChannel[channel_id]?.timer);
                const timer = setTimeout(() => {
                    delete state.byChannel[channel_id];
                }, 90000);
                state.byChannel[channel_id] = { statusText: status_text, timer };
            } else {
                clearTimeout(state.byChannel[channel_id]?.timer);
                delete state.byChannel[channel_id];
            }
        });

        return state;
    },
});
