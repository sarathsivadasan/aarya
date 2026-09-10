/** @odoo-module **/
/**
 * ODEX AI Assistant - AI Message Component
 * Renders individual chat messages with markdown, code blocks, and actions.
 */

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AiMessage extends Component {
    static template = "odex_ai_assistant.AiMessage";
    static props = {
        message: Object,
        onCopy: { type: Function, optional: true },
        onFeedback: { type: Function, optional: true },
        onPostToChatter: { type: Function, optional: true },
    };

    setup() {
        this.groqService = useService("odex_groq_service");
        this.state = useState({
            isCopied: false,
            showActions: false,
            feedbackGiven: null,
        });
        this.contentRef = useRef("messageContent");

        onMounted(() => {
            if (this.props.message.role === "assistant" && this.contentRef.el) {
                // Set rendered HTML content
                this.contentRef.el.innerHTML = this.renderedContent;
            }
        });
    }

    get isUser() {
        return this.props.message.role === "user";
    }

    get isAssistant() {
        return this.props.message.role === "assistant";
    }

    get isStreaming() {
        return this.props.message.isStreaming;
    }

    get isError() {
        return this.props.message.isError;
    }

    get renderedContent() {
        if (this.isUser) {
            // User messages: escape HTML only
            return (this.props.message.content || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/\n/g, "<br/>");
        }
        return this.groqService.formatAIResponse(this.props.message.content || "");
    }

    get formattedTime() {
        return this.groqService.formatMessageTime(this.props.message.create_date);
    }

    get modelBadge() {
        const model = this.props.message.model_used;
        if (!model) return "";
        // Groq / Meta models
        if (model.includes("llama"))    return "Llama";
        if (model.includes("deepseek")) return "DeepSeek";
        if (model.includes("mixtral"))  return "Mixtral";
        if (model.includes("gemma"))    return "Gemma";
        // Claude
        if (model.includes("claude-sonnet-4")) return "Claude Sonnet";
        if (model.includes("claude-3-5-sonnet")) return "Claude 3.5";
        if (model.includes("claude-3-5-haiku")) return "Haiku";
        if (model.includes("claude-3-opus"))    return "Opus";
        if (model.includes("claude-3-haiku"))   return "Haiku";
        if (model.includes("claude"))           return "Claude";
        // OpenAI
        if (model.includes("gpt-4o-mini")) return "GPT-4o Mini";
        if (model.includes("gpt-4o"))      return "GPT-4o";
        if (model.includes("gpt-4"))       return "GPT-4";
        if (model.includes("gpt-3.5"))     return "GPT-3.5";
        // Gemini
        if (model.includes("gemini-2"))    return "Gemini 2";
        if (model.includes("gemini-1.5-pro"))   return "Gemini Pro";
        if (model.includes("gemini-1.5-flash"))  return "Gemini Flash";
        if (model.includes("gemini"))      return "Gemini";
        // Ollama (local)
        if (model.includes("mistral"))     return "Mistral";
        if (model.includes("codellama"))   return "CodeLlama";
        if (model.includes("phi"))         return "Phi";
        // Fallback
        return model.split(":")[0].split("-")[0];
    }

    async onCopy() {
        const content = this.props.message.content || "";
        try {
            await navigator.clipboard.writeText(content);
            this.state.isCopied = true;
            setTimeout(() => { this.state.isCopied = false; }, 2000);
        } catch (e) {
            console.error("Copy failed:", e);
        }
        if (this.props.onCopy) {
            this.props.onCopy(content);
        }
    }

    onFeedback(type) {
        this.state.feedbackGiven = type;
        if (this.props.onFeedback) {
            this.props.onFeedback(this.props.message.id, type);
        }
    }

    onPostToChatter() {
        if (this.props.onPostToChatter) {
            this.props.onPostToChatter(this.props.message);
        }
    }

    onMouseEnter() {
        this.state.showActions = true;
    }

    onMouseLeave() {
        this.state.showActions = false;
    }
}
