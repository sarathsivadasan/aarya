/** @odoo-module **/
/**
 * ODEX AI Assistant - Provider Utilities Service
 * Metadata, formatting helpers, and suggested prompts.
 * Provider-agnostic — works with Groq, Claude, OpenAI, Gemini, Ollama.
 */

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const serviceRegistry = registry.category("services");

// ── Provider catalogue ──────────────────────────────────────────────────
export const PROVIDERS = {
    groq: {
        label: "Groq",
        icon: "fa-bolt",
        color: "#f55036",
        description: "Ultra-fast inference — free tier available",
        docsUrl: "https://console.groq.com",
        models: [
            { id: "llama-3.3-70b-versatile",       name: "Llama 3.3 70B",      badge: "Recommended" },
            { id: "deepseek-r1-distill-llama-70b",  name: "DeepSeek R1 70B",    badge: "Reasoning" },
            { id: "mixtral-8x7b-32768",             name: "Mixtral 8x7B 32K",   badge: "Long context" },
            { id: "llama-3.1-8b-instant",           name: "Llama 3.1 8B",       badge: "Fast" },
            { id: "gemma2-9b-it",                   name: "Gemma 2 9B",         badge: "Google" },
        ],
    },
    claude: {
        label: "Claude (Anthropic)",
        icon: "fa-star",
        color: "#d97706",
        description: "State-of-the-art reasoning and safety",
        docsUrl: "https://console.anthropic.com",
        models: [
            { id: "claude-sonnet-4-5",          name: "Claude Sonnet 4.5",  badge: "Latest" },
            { id: "claude-3-5-sonnet-20241022",  name: "Claude 3.5 Sonnet", badge: "Powerful" },
            { id: "claude-3-5-haiku-20241022",   name: "Claude 3.5 Haiku",  badge: "Fast" },
            { id: "claude-3-opus-20240229",      name: "Claude 3 Opus",     badge: "Most capable" },
            { id: "claude-3-haiku-20240307",     name: "Claude 3 Haiku",    badge: "Fastest" },
        ],
    },
    openai: {
        label: "OpenAI",
        icon: "fa-code",
        color: "#10a37f",
        description: "GPT-4o and GPT-3.5 models",
        docsUrl: "https://platform.openai.com",
        models: [
            { id: "gpt-4o",        name: "GPT-4o",         badge: "Recommended" },
            { id: "gpt-4o-mini",   name: "GPT-4o Mini",    badge: "Fast & cheap" },
            { id: "gpt-4-turbo",   name: "GPT-4 Turbo",    badge: "Powerful" },
            { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo",  badge: "Budget" },
        ],
    },
    gemini: {
        label: "Google Gemini",
        icon: "fa-google",
        color: "#4285f4",
        description: "Google's multimodal AI — free tier available",
        docsUrl: "https://aistudio.google.com",
        models: [
            { id: "gemini-1.5-pro",       name: "Gemini 1.5 Pro",           badge: "Powerful" },
            { id: "gemini-1.5-flash",     name: "Gemini 1.5 Flash",         badge: "Fast" },
            { id: "gemini-2.0-flash-exp", name: "Gemini 2.0 Flash",         badge: "Experimental" },
        ],
    },
    ollama: {
        label: "Ollama (Local)",
        icon: "fa-server",
        color: "#6366f1",
        description: "Run LLMs locally — no API key needed",
        docsUrl: "https://ollama.com",
        models: [
            { id: "llama3.2",   name: "Llama 3.2",    badge: "Popular" },
            { id: "llama3.1",   name: "Llama 3.1",    badge: "Stable" },
            { id: "mistral",    name: "Mistral",       badge: "Fast" },
            { id: "codellama",  name: "CodeLlama",     badge: "Coding" },
            { id: "phi3",       name: "Phi-3",         badge: "Small" },
        ],
    },
};

// ── Suggested prompts ───────────────────────────────────────────────────
export const SUGGESTED_PROMPTS = [
    {
        category: "General",
        icon: "fa-magic",
        prompts: [
            "Summarize the current record for me",
            "What are the key action items here?",
            "Draft a professional response",
            "Explain what I need to do next",
        ],
    },
    {
        category: "Vehicle & Workshop",
        icon: "fa-car",
        prompts: [
            "Analyze this vehicle's maintenance history",
            "Predict upcoming maintenance requirements",
            "Generate a vehicle health score",
            "Calculate total vehicle ownership cost",
            "Auto-generate job card description",
            "Suggest required spare parts for this repair",
            "Create a customer-friendly delivery note",
            "Identify frequently replaced spare parts",
        ],
    },
    {
        category: "Sales & CRM",
        icon: "fa-handshake-o",
        prompts: [
            "Analyze this opportunity and suggest next steps",
            "Draft a follow-up email for this customer",
            "Assess the win probability for this deal",
            "Create a 30-day follow-up schedule",
        ],
    },
    {
        category: "Finance",
        icon: "fa-money",
        prompts: [
            "Analyze this invoice for discrepancies",
            "Draft a payment follow-up message",
            "Summarize the financial position",
            "Identify unusual expense patterns",
        ],
    },
    {
        category: "Project & Tasks",
        icon: "fa-tasks",
        prompts: [
            "Break this task into smaller steps",
            "Estimate the time needed for this project",
            "Identify blockers and suggest solutions",
            "Generate a project status report",
        ],
    },
];

export const groqService = {
    dependencies: [],

    start(env) {

        function getProviders() { return PROVIDERS; }

        function getProviderInfo(providerId) {
            return PROVIDERS[providerId] || PROVIDERS.groq;
        }

        function getModelBadge(modelId, providerId) {
            const provider = PROVIDERS[providerId];
            if (!provider) return "";
            const model = provider.models.find((m) => m.id === modelId);
            return model ? model.badge : "";
        }

        function getProviderLabel(providerId) {
            return PROVIDERS[providerId]?.label || providerId;
        }

        function getSuggestedPrompts(resModel = null) {
            if (!resModel) return SUGGESTED_PROMPTS;
            const vehicleModels = ["fleet.vehicle", "fleet.vehicle.log.services", "fleet.vehicle.log.fuel"];
            const crmModels = ["crm.lead", "sale.order", "account.move"];
            return SUGGESTED_PROMPTS.filter((cat) => {
                if (cat.category === "Vehicle & Workshop") return vehicleModels.includes(resModel);
                if (cat.category === "Sales & CRM") return crmModels.includes(resModel);
                return true;
            });
        }

        async function getTemplatesForModel(resModel) {
            try {
                const result = await rpc("/odex_ai/get_templates", { res_model: resModel });
                return result.templates || [];
            } catch (e) {
                console.error("[ODEX AI] Failed to fetch templates:", e);
                return [];
            }
        }

        async function testConnection() {
            try {
                return await rpc("/odex_ai/test_connection", {});
            } catch (e) {
                return { success: false, error: String(e) };
            }
        }

        /**
         * Convert AI markdown-like text to safe HTML.
         */
        function formatAIResponse(text) {
            if (!text) return "";
            let html = text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");

            // Fenced code blocks
            html = html.replace(
                /```(\w*)\n?([\s\S]*?)```/g,
                (_, lang, code) => {
                    const label = lang
                        ? `<span class="odex-ai-code-lang">${lang}</span>`
                        : "";
                    return (
                        `<div class="odex-ai-code-block">${label}` +
                        `<button class="odex-ai-copy-code" onclick="odexAiCopyCode(this)" title="Copy">` +
                        `<i class="fa fa-copy"></i></button>` +
                        `<pre><code>${code.trim()}</code></pre></div>`
                    );
                }
            );
            // Inline code
            html = html.replace(/`([^`]+)`/g, "<code class='odex-ai-inline-code'>$1</code>");
            // Headers
            html = html.replace(/^### (.+)$/gm, "<h5 class='odex-ai-h5'>$1</h5>");
            html = html.replace(/^## (.+)$/gm,  "<h4 class='odex-ai-h4'>$1</h4>");
            html = html.replace(/^# (.+)$/gm,   "<h3 class='odex-ai-h3'>$1</h3>");
            // Bold / italic
            html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
            html = html.replace(/\*([^*\n]+)\*/g,  "<em>$1</em>");
            // Lists
            html = html.replace(/^[*-] (.+)$/gm, "<li>$1</li>");
            html = html.replace(/(<li>[\s\S]*?<\/li>\n?)+/g, (m) => {
                if (!m.includes("<ol")) return `<ul class='odex-ai-list'>${m}</ul>`;
                return m;
            });
            html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
            // Paragraphs
            html = html.replace(/\n\n/g, "</p><p class='odex-ai-para'>");
            html = html.replace(/\n/g, "<br/>");
            if (!html.match(/^<(h[1-5]|ul|ol|div|p)/)) {
                html = `<p class='odex-ai-para'>${html}</p>`;
            }
            return html;
        }

        // Copy code block helper (called from inline onclick)
        window.odexAiCopyCode = function (btn) {
            const code = btn.nextElementSibling?.querySelector("code")?.textContent;
            if (code) {
                navigator.clipboard.writeText(code).then(() => {
                    btn.innerHTML = '<i class="fa fa-check"></i>';
                    setTimeout(() => { btn.innerHTML = '<i class="fa fa-copy"></i>'; }, 2000);
                });
            }
        };

        function formatMessageTime(dateStr) {
            if (!dateStr) return "";
            const d = new Date(dateStr);
            const diffMs = Date.now() - d;
            const mins  = Math.floor(diffMs / 60000);
            const hours = Math.floor(diffMs / 3600000);
            const days  = Math.floor(diffMs / 86400000);
            if (mins  <  1) return "Just now";
            if (mins  < 60) return `${mins}m ago`;
            if (hours < 24) return `${hours}h ago`;
            if (days  <  7) return `${days}d ago`;
            return d.toLocaleDateString();
        }

        function truncateText(text, max = 100) {
            if (!text) return "";
            const plain = text.replace(/<[^>]+>/g, "");
            return plain.length > max ? plain.slice(0, max) + "…" : plain;
        }

        return {
            getProviders,
            getProviderInfo,
            getModelBadge,
            getProviderLabel,
            getSuggestedPrompts,
            getTemplatesForModel,
            testConnection,
            formatAIResponse,
            formatMessageTime,
            truncateText,
            PROVIDERS,
            SUGGESTED_PROMPTS,
        };
    },
};

serviceRegistry.add("odex_groq_service", groqService);
