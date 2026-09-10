# -*- coding: utf-8 -*-
"""
ODEX AI Assistant — Multi-Provider Service Layer
=================================================
Abstracts all AI provider API calls behind a single interface.
Supported providers:
  - Groq          (llama, deepseek, mixtral, gemma)
  - Claude        (Anthropic: claude-3-5-sonnet, claude-3-haiku, etc.)
  - OpenAI        (gpt-4o, gpt-4o-mini, gpt-3.5-turbo, etc.)
  - Gemini        (Google: gemini-1.5-pro, gemini-1.5-flash)
  - Ollama        (local LLMs: llama3, mistral, codellama, etc.)

To add a new provider:
  1. Add its models to PROVIDER_MODELS
  2. Add its API call logic to AiProviderService._call_provider()
  3. Add its config key to res_config_settings.py
"""

import json
import logging
import time
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ============================================================
# Provider endpoint constants
# ============================================================
GROQ_API_URL    = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_API_URL  = "https://api.openai.com/v1/chat/completions"
CLAUDE_API_URL  = "https://api.anthropic.com/v1/messages"
GEMINI_API_URL  = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OLLAMA_API_URL  = "{base_url}/api/chat"      # base_url from settings, default http://localhost:11434

CLAUDE_API_VERSION = "2023-06-01"

# ============================================================
# Model registry per provider
# ============================================================
PROVIDER_MODELS = {
    "groq": [
        ("llama-3.3-70b-versatile",        "Llama 3.3 70B Versatile (Recommended)"),
        ("deepseek-r1-distill-llama-70b",  "DeepSeek R1 Distill Llama 70B"),
        ("mixtral-8x7b-32768",             "Mixtral 8x7B 32K"),
        ("llama-3.1-8b-instant",           "Llama 3.1 8B Instant (Fast)"),
        ("gemma2-9b-it",                   "Gemma 2 9B IT"),
    ],
    "claude": [
        ("claude-sonnet-4-5",              "Claude Sonnet 4.5 (Recommended)"),
        ("claude-3-5-sonnet-20241022",     "Claude 3.5 Sonnet"),
        ("claude-3-5-haiku-20241022",      "Claude 3.5 Haiku (Fast)"),
        ("claude-3-opus-20240229",         "Claude 3 Opus (Most capable)"),
        ("claude-3-haiku-20240307",        "Claude 3 Haiku (Fastest)"),
    ],
    "openai": [
        ("gpt-4o",                         "GPT-4o (Recommended)"),
        ("gpt-4o-mini",                    "GPT-4o Mini (Fast & cheap)"),
        ("gpt-4-turbo",                    "GPT-4 Turbo"),
        ("gpt-3.5-turbo",                  "GPT-3.5 Turbo"),
    ],
    "gemini": [
        ("gemini-1.5-pro",                 "Gemini 1.5 Pro"),
        ("gemini-1.5-flash",               "Gemini 1.5 Flash (Fast)"),
        ("gemini-2.0-flash-exp",           "Gemini 2.0 Flash (Experimental)"),
    ],
    "ollama": [
        ("llama3.2",                       "Llama 3.2 (local)"),
        ("llama3.1",                       "Llama 3.1 (local)"),
        ("mistral",                        "Mistral (local)"),
        ("codellama",                      "CodeLlama (local)"),
        ("phi3",                           "Phi-3 (local)"),
        ("custom",                         "Custom model name"),
    ],
}


class AiProviderService(models.AbstractModel):
    """
    Abstract service layer for AI provider calls.
    Used by the controller to call any configured provider.
    """
    _name = "odex.ai.provider.service"
    _description = "ODEX AI Provider Service"

    @api.model
    def get_provider_config(self):
        """
        Read all provider settings from ir.config_parameter.
        Returns a dict with everything needed to make an API call.
        """
        params = self.env["ir.config_parameter"].sudo()
        provider = params.get_param("odex_ai_assistant.provider", "groq")
        return {
            "provider":          provider,
            "model":             params.get_param("odex_ai_assistant.model", "llama-3.3-70b-versatile"),
            "temperature":       float(params.get_param("odex_ai_assistant.temperature", "0.7")),
            "max_tokens":        int(params.get_param("odex_ai_assistant.max_tokens", "2048")),
            "streaming_enabled": params.get_param("odex_ai_assistant.streaming_enabled", "True") == "True",
            "system_prompt":     params.get_param(
                "odex_ai_assistant.system_prompt",
                "You are ODEX AI Assistant, an intelligent assistant integrated into Odoo ERP."
            ),
            "context_window":    int(params.get_param("odex_ai_assistant.context_window", "20")),
            # Provider API keys
            "groq_api_key":      params.get_param("odex_ai_assistant.api_key", ""),
            "claude_api_key":    params.get_param("odex_ai_assistant.claude_api_key", ""),
            "openai_api_key":    params.get_param("odex_ai_assistant.openai_api_key", ""),
            "gemini_api_key":    params.get_param("odex_ai_assistant.gemini_api_key", ""),
            "ollama_base_url":   params.get_param("odex_ai_assistant.ollama_base_url", "http://localhost:11434"),
        }

    @api.model
    def get_active_api_key(self, config):
        """Return the API key for the active provider."""
        provider = config.get("provider", "groq")
        key_map = {
            "groq":   config.get("groq_api_key", ""),
            "claude": config.get("claude_api_key", ""),
            "openai": config.get("openai_api_key", ""),
            "gemini": config.get("gemini_api_key", ""),
            "ollama": "local",   # Ollama runs locally, no key needed
        }
        key = key_map.get(provider, "")
        if not key and provider != "ollama":
            raise UserError(_(
                f"API key for {provider.title()} is not configured. "
                f"Go to Settings → AI Assistant to add it."
            ))
        return key

    @api.model
    def call_provider(self, messages, config, stream=False):
        """
        Route the API call to the correct provider.
        Returns a requests.Response object (use .json() or iter_lines()).

        :param messages: list of {"role": "...", "content": "..."} dicts
        :param config:   dict from get_provider_config()
        :param stream:   bool — whether to request streaming
        """
        provider = config.get("provider", "groq")
        api_key = self.get_active_api_key(config)

        dispatch = {
            "groq":   self._call_groq,
            "claude": self._call_claude,
            "openai": self._call_openai,
            "gemini": self._call_gemini,
            "ollama": self._call_ollama,
        }
        fn = dispatch.get(provider)
        if not fn:
            raise UserError(_(f"Unknown AI provider: {provider}"))

        _logger.info("ODEX AI: calling provider=%s model=%s stream=%s", provider, config.get("model"), stream)
        return fn(messages, config, api_key, stream)

    # ----------------------------------------------------------
    # GROQ  (OpenAI-compatible endpoint)
    # ----------------------------------------------------------
    def _call_groq(self, messages, config, api_key, stream):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model":       config["model"],
            "messages":    messages,
            "temperature": config["temperature"],
            "max_tokens":  config["max_tokens"],
            "stream":      stream,
        }
        return self._post(GROQ_API_URL, headers, payload, stream, "Groq")

    # ----------------------------------------------------------
    # OPENAI  (same structure as Groq)
    # ----------------------------------------------------------
    def _call_openai(self, messages, config, api_key, stream):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model":       config["model"],
            "messages":    messages,
            "temperature": config["temperature"],
            "max_tokens":  config["max_tokens"],
            "stream":      stream,
        }
        return self._post(OPENAI_API_URL, headers, payload, stream, "OpenAI")

    # ----------------------------------------------------------
    # CLAUDE (Anthropic) — different request/response format
    # ----------------------------------------------------------
    def _call_claude(self, messages, config, api_key, stream):
        """
        Anthropic's /v1/messages endpoint.
        - System prompt is a top-level field, not a message role.
        - Response format differs from OpenAI.
        - Streaming uses 'content_block_delta' events.
        """
        headers = {
            "x-api-key":         api_key,
            "anthropic-version": CLAUDE_API_VERSION,
            "Content-Type":      "application/json",
        }

        # Separate system prompt from messages
        system_content = config.get("system_prompt", "")
        api_messages = [m for m in messages if m["role"] != "system"]

        # Anthropic requires alternating user/assistant roles
        # and the first message must be from the user
        api_messages = self._normalize_message_roles(api_messages)

        payload = {
            "model":      config["model"],
            "max_tokens": config["max_tokens"],
            "messages":   api_messages,
            "stream":     stream,
        }
        if system_content:
            payload["system"] = system_content

        # temperature is optional for Claude (0.0–1.0)
        temp = min(config.get("temperature", 0.7), 1.0)
        payload["temperature"] = temp

        resp = self._post(CLAUDE_API_URL, headers, payload, stream, "Claude")

        # Wrap Claude response in a unified adapter so the controller
        # can call .json() / iter_lines() the same way as OpenAI-style
        if not stream:
            return ClaudeResponseAdapter(resp)
        return ClaudeStreamAdapter(resp)

    # ----------------------------------------------------------
    # GEMINI (Google)
    # ----------------------------------------------------------
    def _call_gemini(self, messages, config, api_key, stream):
        """
        Google Gemini REST API.
        Converts OpenAI-style messages to Gemini 'contents' format.
        """
        model = config["model"]
        url = GEMINI_API_URL.format(model=model)
        if stream:
            url = url.replace(":generateContent", ":streamGenerateContent") + "?alt=sse"
        url += f"{'&' if '?' in url else '?'}key={api_key}"

        # Convert messages → Gemini format
        contents = []
        system_text = ""
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            elif msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature":   config["temperature"],
                "maxOutputTokens": config["max_tokens"],
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        headers = {"Content-Type": "application/json"}
        resp = self._post(url, headers, payload, stream, "Gemini")
        if not stream:
            return GeminiResponseAdapter(resp)
        return GeminiStreamAdapter(resp)

    # ----------------------------------------------------------
    # OLLAMA (local)
    # ----------------------------------------------------------
    def _call_ollama(self, messages, config, api_key, stream):
        """
        Ollama local API — OpenAI-compatible /api/chat endpoint.
        Runs on localhost:11434 by default.
        """
        base_url = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model":    config["model"],
            "messages": messages,
            "stream":   stream,
            "options": {
                "temperature": config["temperature"],
                "num_predict": config["max_tokens"],
            },
        }
        try:
            return self._post(url, headers, payload, stream, "Ollama")
        except UserError as e:
            # Give a more helpful error for local connection failures
            if "ConnectionError" in str(e) or "Connection" in str(e):
                raise UserError(_(
                    "Cannot connect to Ollama at %s. "
                    "Make sure Ollama is running: `ollama serve`"
                ) % base_url)
            raise

    # ----------------------------------------------------------
    # Shared HTTP POST
    # ----------------------------------------------------------
    def _post(self, url, headers, payload, stream, provider_name):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
                stream=stream,
            )
            # Common error handling
            if resp.status_code == 401:
                raise UserError(_(f"Invalid {provider_name} API key. Check your settings."))
            elif resp.status_code == 429:
                raise UserError(_(f"{provider_name} rate limit exceeded. Please wait and try again."))
            elif resp.status_code == 400:
                try:
                    detail = resp.json()
                    err = (detail.get("error", {}) or {}).get("message", "") or str(detail)
                except Exception:
                    err = resp.text[:200]
                raise UserError(_(f"{provider_name} API error: {err}"))
            elif resp.status_code == 529:
                raise UserError(_(f"{provider_name} is overloaded. Please try again in a moment."))
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout:
            raise UserError(_(f"{provider_name} API timed out. Please try again."))
        except requests.exceptions.ConnectionError as e:
            raise UserError(_(f"Could not connect to {provider_name}: {e}"))

    @staticmethod
    def _normalize_message_roles(messages):
        """
        Anthropic requires strictly alternating user/assistant roles.
        Merges consecutive same-role messages.
        """
        if not messages:
            return [{"role": "user", "content": "Hello"}]
        result = []
        for msg in messages:
            if result and result[-1]["role"] == msg["role"]:
                result[-1]["content"] += "\n\n" + msg["content"]
            else:
                result.append({"role": msg["role"], "content": msg["content"]})
        # Must start with 'user'
        if result[0]["role"] != "user":
            result.insert(0, {"role": "user", "content": "Continue."})
        return result

    @api.model
    def extract_content_from_response(self, response, provider):
        """
        Extract the text content from a completed (non-streaming) API response.
        Normalises across all providers.
        """
        try:
            if provider in ("groq", "openai"):
                data = response.json()
                return data["choices"][0]["message"]["content"], data.get("usage", {})

            elif provider == "claude":
                # ClaudeResponseAdapter already normalises this
                if hasattr(response, "odex_content"):
                    return response.odex_content, response.odex_usage
                data = response.json()
                content = data["content"][0]["text"]
                usage = {
                    "prompt_tokens":     data.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                    "total_tokens": (
                        data.get("usage", {}).get("input_tokens", 0) +
                        data.get("usage", {}).get("output_tokens", 0)
                    ),
                }
                return content, usage

            elif provider == "gemini":
                if hasattr(response, "odex_content"):
                    return response.odex_content, response.odex_usage
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                usage = {
                    "prompt_tokens":     data.get("usageMetadata", {}).get("promptTokenCount", 0),
                    "completion_tokens": data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
                    "total_tokens":      data.get("usageMetadata", {}).get("totalTokenCount", 0),
                }
                return content, usage

            elif provider == "ollama":
                data = response.json()
                content = data["message"]["content"]
                return content, {"total_tokens": data.get("eval_count", 0)}

        except Exception as e:
            _logger.error("ODEX AI: failed to extract content from %s response: %s", provider, e)
            raise UserError(_(f"Failed to parse {provider} response: {e}"))

    @api.model
    def iter_stream_tokens(self, response, provider):
        """
        Generator that yields (token_str, is_done) tuples from a streaming response.
        Normalises SSE/NDJSON formats across all providers.
        """
        if provider in ("groq", "openai"):
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        yield "", True
                        return
                    try:
                        chunk = json.loads(data_str)
                        token = chunk["choices"][0].get("delta", {}).get("content", "")
                        if token:
                            yield token, False
                    except (json.JSONDecodeError, KeyError):
                        pass

        elif provider == "claude":
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        chunk = json.loads(data_str)
                        event_type = chunk.get("type", "")
                        if event_type == "content_block_delta":
                            token = chunk.get("delta", {}).get("text", "")
                            if token:
                                yield token, False
                        elif event_type == "message_stop":
                            yield "", True
                            return
                    except (json.JSONDecodeError, KeyError):
                        pass

        elif provider == "gemini":
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        chunk = json.loads(data_str)
                        parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        for part in parts:
                            token = part.get("text", "")
                            if token:
                                yield token, False
                        if chunk.get("candidates", [{}])[0].get("finishReason") == "STOP":
                            yield "", True
                            return
                    except (json.JSONDecodeError, KeyError):
                        pass

        elif provider == "ollama":
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token, False
                    if chunk.get("done"):
                        yield "", True
                        return
                except json.JSONDecodeError:
                    pass


# ============================================================
# Response Adapters (normalise non-OpenAI response shapes)
# ============================================================

class ClaudeResponseAdapter:
    """Wraps a raw Claude /v1/messages response to look like an OpenAI response."""
    def __init__(self, resp):
        self._resp = resp
        data = resp.json()
        self.odex_content = data["content"][0]["text"]
        usage = data.get("usage", {})
        self.odex_usage = {
            "prompt_tokens":     usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens":      usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

    def json(self):
        return self._resp.json()

    def iter_lines(self):
        return self._resp.iter_lines()


class ClaudeStreamAdapter:
    """Wraps a streaming Claude response."""
    def __init__(self, resp):
        self._resp = resp

    def iter_lines(self):
        return self._resp.iter_lines()


class GeminiResponseAdapter:
    """Wraps a raw Gemini generateContent response."""
    def __init__(self, resp):
        self._resp = resp
        data = resp.json()
        self.odex_content = data["candidates"][0]["content"]["parts"][0]["text"]
        meta = data.get("usageMetadata", {})
        self.odex_usage = {
            "prompt_tokens":     meta.get("promptTokenCount", 0),
            "completion_tokens": meta.get("candidatesTokenCount", 0),
            "total_tokens":      meta.get("totalTokenCount", 0),
        }

    def json(self):
        return self._resp.json()


class GeminiStreamAdapter:
    """Wraps a streaming Gemini SSE response."""
    def __init__(self, resp):
        self._resp = resp

    def iter_lines(self):
        return self._resp.iter_lines()
