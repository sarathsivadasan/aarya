/** @odoo-module **/
/**
 * ODEX AI Assistant - Main AI Panel Component
 * The primary floating/sidebar chat interface.
 */

import { Component, useState, useRef, useEffect, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AiMessage } from "./ai_message";

export class AiPanel extends Component {
    static template = "odex_ai_assistant.AiPanel";
    static components = { AiMessage };
    static props = {};

    setup() {
        this.aiService = useService("odex_ai_service");
        this.groqService = useService("odex_groq_service");
        this.notification = useService("notification");

        this.state = useState({
            inputValue: "",
            isLoadingConversations: false,
            showSidebar: true,
            showSuggestedPrompts: false,
            showTemplates: false,
            templates: [],
            suggestedPrompts: [],
            searchQuery: "",
            isDragging: false,
            dragStartX: 0,
            dragStartY: 0,
            panelX: null,
            panelY: null,
            activeTab: "chat", // chat | history | templates
            showScrollButton: false,
        });

        this.messagesEndRef = useRef("messagesEnd");
        this.inputRef = useRef("chatInput");
        this.messagesContainerRef = useRef("messagesContainer");
        this.panelRef = useRef("panel");

        onMounted(() => {
            this._loadInitialData();
            this._setupKeyboardShortcuts();
            this._setupScrollListener();
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this._handleKeydown);
        });
    }

    get aiState() {
        return this.aiService.state;
    }

    get activeConversation() {
        const id = this.aiState.activeConversationId;
        return this.aiState.conversations.find((c) => c.id === id) || null;
    }

    get filteredConversations() {
        const q = this.state.searchQuery.toLowerCase();
        if (!q) return this.aiState.conversations;
        return this.aiState.conversations.filter(
            (c) => c.name.toLowerCase().includes(q) || (c.last_message || "").toLowerCase().includes(q)
        );
    }

    get hasMessages() {
        return this.aiState.messages && this.aiState.messages.length > 0;
    }

    get isFloating() {
        return this.aiState.panelPosition === "floating";
    }

    get panelStyle() {
        if (this.isFloating && this.state.panelX !== null) {
            return `left: ${this.state.panelX}px; top: ${this.state.panelY}px;`;
        }
        return "";
    }

    async _loadInitialData() {
        this.state.isLoadingConversations = true;
        try {
            await this.aiService.loadConversations();
            // Load suggested prompts
            this.state.suggestedPrompts = this.groqService.getSuggestedPrompts(
                this.aiState.activeResModel
            );
            // Load templates
            const templates = await this.groqService.getTemplatesForModel(
                this.aiState.activeResModel
            );
            this.state.templates = templates;
        } finally {
            this.state.isLoadingConversations = false;
        }
    }

    _setupKeyboardShortcuts() {
        this._handleKeydown = (e) => {
            // Escape to close
            if (e.key === "Escape" && this.aiState.isOpen) {
                this.aiService.closePanel();
            }
        };
        document.addEventListener("keydown", this._handleKeydown);
    }

    _setupScrollListener() {
        const checkScroll = () => {
            const container = this.messagesContainerRef.el;
            if (container) {
                const isNearBottom =
                    container.scrollHeight - container.scrollTop - container.clientHeight < 150;
                this.state.showScrollButton = !isNearBottom && container.scrollHeight > container.clientHeight;
            }
        };
        // Will be attached when container renders
        this._scrollChecker = checkScroll;
    }

    scrollToBottom(smooth = true) {
        const el = this.messagesEndRef.el;
        if (el) {
            el.scrollIntoView({ behavior: smooth ? "smooth" : "instant" });
        }
        this.state.showScrollButton = false;
    }

    // ==================== ACTIONS ====================

    async onSelectConversation(conversationId) {
        await this.aiService.loadConversation(conversationId);
        this.state.activeTab = "chat";
        setTimeout(() => this.scrollToBottom(false), 100);
    }

    async onNewConversation() {
        await this.aiService.newConversation();
        this.state.activeTab = "chat";
        this.state.inputValue = "";
    }

    async onDeleteConversation(e, conversationId) {
        e.stopPropagation();
        await this.aiService.deleteConversation(conversationId);
    }

    async onPinConversation(e, conversationId, currentPinned) {
        e.stopPropagation();
        await this.aiService.pinConversation(conversationId, !currentPinned);
    }

    onInputChange(e) {
        this.state.inputValue = e.target.value;
        this.aiService.state.inputValue = e.target.value;
        // Auto-resize textarea
        const ta = e.target;
        ta.style.height = "auto";
        ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
    }

    async onSendMessage() {
        const message = this.state.inputValue.trim();
        if (!message || this.aiState.isLoading || this.aiState.isStreaming) return;
        this.state.inputValue = "";
        if (this.inputRef.el) {
            this.inputRef.el.style.height = "auto";
        }
        await this.aiService.sendMessage(message);
        setTimeout(() => this.scrollToBottom(), 50);
    }

    onKeyDown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.onSendMessage();
        }
    }

    onUseSuggestedPrompt(prompt) {
        this.state.inputValue = prompt;
        this.state.showSuggestedPrompts = false;
        if (this.inputRef.el) {
            this.inputRef.el.focus();
            this.inputRef.el.style.height = "auto";
            this.inputRef.el.style.height = Math.min(this.inputRef.el.scrollHeight, 200) + "px";
        }
    }

    onUseTemplate(template) {
        this.state.inputValue = template.prompt_text;
        this.state.showTemplates = false;
        this.state.activeTab = "chat";
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    async onSummarizeRecord() {
        if (!this.aiState.activeResModel || !this.aiState.activeResId) {
            this.notification.add("No active record to summarize. Open a record first.", {
                type: "warning",
            });
            return;
        }
        const message = `Please provide a comprehensive summary of this ${this.aiState.activeResName || "record"}.`;
        this.state.inputValue = message;
        await this.onSendMessage();
    }

    async onExportConversation() {
        if (!this.aiState.activeConversationId) return;
        await this.aiService.exportConversation(this.aiState.activeConversationId);
    }

    onClosePanel() {
        this.aiService.closePanel();
    }

    onMinimize() {
        this.aiService.minimizePanel();
    }

    onToggleFullscreen() {
        this.aiService.toggleFullscreen();
    }

    onToggleSidebar() {
        this.state.showSidebar = !this.state.showSidebar;
    }

    onSearchChange(e) {
        this.state.searchQuery = e.target.value;
    }

    onClearChat() {
        if (this.aiState.activeConversationId) {
            this.aiService.loadConversation(this.aiState.activeConversationId);
        }
        this.aiService.state.messages = [];
    }

    // ==================== DRAG (FLOATING) ====================

    onDragStart(e) {
        if (!this.isFloating) return;
        this.state.isDragging = true;
        const rect = this.panelRef.el.getBoundingClientRect();
        this.state.dragStartX = e.clientX - rect.left;
        this.state.dragStartY = e.clientY - rect.top;

        const onMove = (moveEvent) => {
            if (!this.state.isDragging) return;
            this.state.panelX = moveEvent.clientX - this.state.dragStartX;
            this.state.panelY = moveEvent.clientY - this.state.dragStartY;
        };
        const onUp = () => {
            this.state.isDragging = false;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }

    // ==================== COPY ====================

    async onCopyMessage(content) {
        try {
            const plain = content.replace(/<[^>]+>/g, "");
            await navigator.clipboard.writeText(plain);
            this.notification.add("Copied to clipboard!", { type: "success", sticky: false });
        } catch (e) {
            console.error("Copy failed:", e);
        }
    }

    onTabSwitch(tab) {
        this.state.activeTab = tab;
        if (tab === "chat") {
            setTimeout(() => this.scrollToBottom(false), 50);
        }
    }

    onScrollMessages(e) {
        const container = e.target;
        const isNearBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight < 150;
        this.state.showScrollButton = !isNearBottom && container.scrollHeight > container.clientHeight;
    }

    formatTime(dateStr) {
        return this.groqService.formatMessageTime(dateStr);
    }

    truncate(text, len = 80) {
        return this.groqService.truncateText(text, len);
    }
}
