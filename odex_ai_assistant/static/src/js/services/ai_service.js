/** @odoo-module **/
/**
 * ODEX AI Assistant - Core AI Service
 * Manages conversation state, API calls, and reactive data for the AI panel.
 */

import { reactive, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";

const serviceRegistry = registry.category("services");

export const aiService = {
    dependencies: ["bus_service", "notification", "user"],

    start(env, { bus_service, notification, user }) {
        // Reactive state for the entire AI Assistant
        const state = reactive({
            // Panel state
            isOpen: false,
            isMinimized: false,
            isFullscreen: false,
            isPinned: false,
            panelPosition: "right", // right | left | floating

            // Conversation state
            conversations: [],
            activeConversationId: null,
            messages: [],
            isLoading: false,
            isStreaming: false,
            streamingContent: "",

            // Config state
            config: {
                hasApiKey: false,
                model: "llama-3.3-70b-versatile",
                streamingEnabled: true,
                aiIcon: "fa-robot",
                panelPosition: "right",
                notificationSound: false,
            },

            // Context state (current active record)
            activeResModel: null,
            activeResId: null,
            activeResName: null,

            // UI state
            searchQuery: "",
            selectedTemplate: null,
            showTemplates: false,
            showSettings: false,
            inputValue: "",
            isInitialized: false,
        });

        // Load config from server
        async function initialize() {
            try {
                const config = await rpc("/odex_ai/get_config", {});
                if (config && !config.error) {
                    state.config = {
                        hasApiKey: config.has_api_key,
                        model: config.model || "llama-3.3-70b-versatile",
                        streamingEnabled: config.streaming_enabled,
                        aiIcon: config.ai_icon || "fa-robot",
                        panelPosition: config.panel_position || "right",
                        notificationSound: config.notification_sound,
                    };
                    state.panelPosition = state.config.panelPosition;
                }
                state.isInitialized = true;
            } catch (e) {
                console.error("[ODEX AI] Failed to initialize config:", e);
                state.isInitialized = true;
            }
        }

        // Panel control
        function openPanel(resModel = null, resId = null, resName = null) {
            state.isOpen = true;
            state.isMinimized = false;
            if (resModel) {
                state.activeResModel = resModel;
                state.activeResId = resId;
                state.activeResName = resName;
            }
            loadConversations();
        }

        function closePanel() {
            state.isOpen = false;
            state.isMinimized = false;
        }

        function togglePanel() {
            if (state.isOpen) {
                closePanel();
            } else {
                openPanel();
            }
        }

        function minimizePanel() {
            state.isMinimized = !state.isMinimized;
        }

        function toggleFullscreen() {
            state.isFullscreen = !state.isFullscreen;
        }

        // Conversation management
        async function loadConversations(searchQuery = "") {
            try {
                const result = await rpc("/odex_ai/get_conversations", {
                    limit: 50,
                    search: searchQuery,
                });
                if (result && result.conversations) {
                    state.conversations = result.conversations;
                }
            } catch (e) {
                console.error("[ODEX AI] Failed to load conversations:", e);
            }
        }

        async function loadConversation(conversationId) {
            try {
                state.isLoading = true;
                const result = await rpc("/odex_ai/get_messages", { conversation_id: conversationId });
                if (result && result.messages) {
                    state.messages = result.messages;
                    state.activeConversationId = conversationId;
                }
            } catch (e) {
                console.error("[ODEX AI] Failed to load conversation:", e);
            } finally {
                state.isLoading = false;
            }
        }

        async function newConversation() {
            try {
                const result = await rpc("/odex_ai/new_conversation", {
                    res_model: state.activeResModel,
                    res_id: state.activeResId,
                });
                if (result && result.conversation_id) {
                    state.activeConversationId = result.conversation_id;
                    state.messages = [];
                    await loadConversations();
                }
            } catch (e) {
                console.error("[ODEX AI] Failed to create conversation:", e);
            }
        }

        async function deleteConversation(conversationId) {
            try {
                await rpc("/odex_ai/delete_conversation", { conversation_id: conversationId });
                if (state.activeConversationId === conversationId) {
                    state.activeConversationId = null;
                    state.messages = [];
                }
                await loadConversations();
            } catch (e) {
                console.error("[ODEX AI] Failed to delete conversation:", e);
            }
        }

        async function pinConversation(conversationId, pinned) {
            try {
                await rpc("/odex_ai/pin_conversation", {
                    conversation_id: conversationId,
                    pinned: pinned,
                });
                await loadConversations();
            } catch (e) {
                console.error("[ODEX AI] Failed to pin conversation:", e);
            }
        }

        // Sending messages
        async function sendMessage(message, options = {}) {
            if (!message || !message.trim() || state.isLoading || state.isStreaming) {
                return;
            }

            const userMsg = {
                id: Date.now(),
                role: "user",
                content: message.trim(),
                create_date: new Date().toISOString(),
                isTemp: true,
            };
            state.messages = [...state.messages, userMsg];
            state.inputValue = "";
            state.isLoading = true;

            try {
                if (state.config.streamingEnabled && !options.forceNonStream) {
                    await sendStreamingMessage(message, options);
                } else {
                    await sendNormalMessage(message, options);
                }
            } catch (e) {
                console.error("[ODEX AI] Send message error:", e);
                state.messages = [
                    ...state.messages.filter((m) => !m.isTemp),
                    {
                        id: Date.now(),
                        role: "assistant",
                        content: "Sorry, an error occurred. Please try again.",
                        isError: true,
                        create_date: new Date().toISOString(),
                    },
                ];
            } finally {
                state.isLoading = false;
                state.isStreaming = false;
                state.streamingContent = "";
            }
        }

        async function sendNormalMessage(message, options = {}) {
            const result = await rpc("/odex_ai/chat", {
                message: message.trim(),
                conversation_id: state.activeConversationId,
                res_model: options.resModel || state.activeResModel,
                res_id: options.resId || state.activeResId,
                post_to_chatter: options.postToChatter || false,
            });

            if (result.error) {
                throw new Error(result.error);
            }

            if (result.success) {
                // Update conversation ID if new
                if (result.conversation_id && result.conversation_id !== state.activeConversationId) {
                    state.activeConversationId = result.conversation_id;
                }
                // Add AI response to messages
                state.messages = [
                    ...state.messages.filter((m) => !m.isTemp),
                    {
                        id: Date.now() + 1,
                        role: "user",
                        content: message.trim(),
                        create_date: new Date().toISOString(),
                    },
                    {
                        id: result.message_id,
                        role: "assistant",
                        content: result.content,
                        tokens_used: result.tokens_used,
                        model_used: result.model,
                        processing_time: result.processing_time,
                        create_date: new Date().toISOString(),
                    },
                ];
                await loadConversations();

                // Play notification sound if enabled
                if (state.config.notificationSound) {
                    playNotificationSound();
                }
            }
        }

        async function sendStreamingMessage(message, options = {}) {
            state.isStreaming = true;
            state.streamingContent = "";

            // Add placeholder for streaming AI message
            const streamingMsgId = Date.now() + 1;
            state.messages = [
                ...state.messages.filter((m) => !m.isTemp),
                {
                    id: Date.now(),
                    role: "user",
                    content: message.trim(),
                    create_date: new Date().toISOString(),
                },
                {
                    id: streamingMsgId,
                    role: "assistant",
                    content: "",
                    isStreaming: true,
                    create_date: new Date().toISOString(),
                },
            ];

            try {
                const response = await browser.fetch("/odex_ai/stream", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        message: message.trim(),
                        conversation_id: state.activeConversationId,
                        res_model: options.resModel || state.activeResModel,
                        res_id: options.resId || state.activeResId,
                    }),
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullContent = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split("\n");

                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (data.token) {
                                    fullContent += data.token;
                                    state.streamingContent = fullContent;
                                    // Update the streaming message
                                    state.messages = state.messages.map((m) =>
                                        m.id === streamingMsgId
                                            ? { ...m, content: fullContent }
                                            : m
                                    );
                                } else if (data.done) {
                                    state.activeConversationId = data.conversation_id || state.activeConversationId;
                                    // Finalize streaming message
                                    state.messages = state.messages.map((m) =>
                                        m.id === streamingMsgId
                                            ? { ...m, content: fullContent, isStreaming: false }
                                            : m
                                    );
                                    state.isStreaming = false;
                                    await loadConversations();
                                    if (state.config.notificationSound) {
                                        playNotificationSound();
                                    }
                                } else if (data.error) {
                                    throw new Error(data.error);
                                }
                            } catch (parseError) {
                                // Skip malformed SSE lines
                            }
                        }
                    }
                }
            } catch (e) {
                state.isStreaming = false;
                // Fall back to non-streaming
                state.messages = state.messages.filter((m) => m.id !== streamingMsgId);
                await sendNormalMessage(message, { ...options, forceNonStream: true });
            }
        }

        function playNotificationSound() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = 880;
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.3);
            } catch (e) {
                // Audio not available
            }
        }

        // Summarize current record
        async function summarizeRecord(resModel, resId, postToChatter = false) {
            state.isLoading = true;
            try {
                const result = await rpc("/odex_ai/summarize_record", {
                    res_model: resModel,
                    res_id: resId,
                    post_to_chatter: postToChatter,
                });
                if (result.success) {
                    return result.summary;
                } else {
                    throw new Error(result.error || "Failed to generate summary");
                }
            } catch (e) {
                throw e;
            } finally {
                state.isLoading = false;
            }
        }

        // Message feedback
        async function submitFeedback(messageId, feedbackType, comment = "") {
            try {
                await rpc("/odex_ai/message_feedback", {
                    message_id: messageId,
                    feedback_type: feedbackType,
                    comment: comment,
                });
            } catch (e) {
                console.error("[ODEX AI] Feedback error:", e);
            }
        }

        // Export conversation
        async function exportConversation(conversationId) {
            try {
                const result = await rpc("/odex_ai/export_conversation", {
                    conversation_id: conversationId,
                });
                if (result.content) {
                    const blob = new Blob([result.content], { type: "text/plain" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `ai-conversation-${result.name || "export"}.txt`;
                    a.click();
                    URL.revokeObjectURL(url);
                }
            } catch (e) {
                console.error("[ODEX AI] Export error:", e);
            }
        }

        // Set active context
        function setContext(resModel, resId, resName) {
            state.activeResModel = resModel;
            state.activeResId = resId;
            state.activeResName = resName;
        }

        // Listen for real-time bus messages
        bus_service.subscribe("odex_ai_message", (payload) => {
            if (payload && state.activeConversationId === payload.conversation_id) {
                // Conversation is active, messages already updated via stream
            }
        });

        // Initialize on start
        initialize();

        return {
            state,
            openPanel,
            closePanel,
            togglePanel,
            minimizePanel,
            toggleFullscreen,
            loadConversations,
            loadConversation,
            newConversation,
            deleteConversation,
            pinConversation,
            sendMessage,
            summarizeRecord,
            submitFeedback,
            exportConversation,
            setContext,
            initialize,
        };
    },
};

serviceRegistry.add("odex_ai_service", aiService);
