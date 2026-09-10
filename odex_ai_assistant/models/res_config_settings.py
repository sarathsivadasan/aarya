# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Extends Odoo configuration settings with ODEX AI Assistant — multi-provider settings."""
    _inherit = 'res.config.settings'

    # ── Active Provider ───────────────────────────────────────────────
    odex_ai_provider = fields.Selection([
        ('groq',   'Groq (Free, Ultra-fast — Recommended)'),
        ('claude', 'Claude by Anthropic'),
        ('openai', 'OpenAI (GPT-4o / GPT-3.5)'),
        ('gemini', 'Google Gemini'),
        ('ollama', 'Ollama (Local LLMs)'),
    ], string='AI Provider',
        config_parameter='odex_ai_assistant.provider',
        default='groq',
    )

    # ── Groq ──────────────────────────────────────────────────────────
    odex_ai_api_key = fields.Char(
        string='Groq API Key',
        config_parameter='odex_ai_assistant.api_key',
        help='Get a free key at console.groq.com',
    )

    # ── Claude (Anthropic) ────────────────────────────────────────────
    odex_ai_claude_api_key = fields.Char(
        string='Claude API Key',
        config_parameter='odex_ai_assistant.claude_api_key',
        help='Get your key at console.anthropic.com',
    )

    # ── OpenAI ────────────────────────────────────────────────────────
    odex_ai_openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='odex_ai_assistant.openai_api_key',
        help='Get your key at platform.openai.com',
    )

    # ── Gemini ────────────────────────────────────────────────────────
    odex_ai_gemini_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='odex_ai_assistant.gemini_api_key',
        help='Get your key at aistudio.google.com',
    )

    # ── Ollama ────────────────────────────────────────────────────────
    odex_ai_ollama_base_url = fields.Char(
        string='Ollama Base URL',
        config_parameter='odex_ai_assistant.ollama_base_url',
        default='http://localhost:11434',
        help='URL where Ollama is running. Default: http://localhost:11434',
    )

    # ── Model selection (provider-specific choices shown via JS) ──────
    odex_ai_model = fields.Char(
        string='Model',
        config_parameter='odex_ai_assistant.model',
        default='llama-3.3-70b-versatile',
        help='Model identifier for the selected provider.',
    )

    # Groq model quick-select
    odex_ai_model_groq = fields.Selection([
        ('llama-3.3-70b-versatile',       'Llama 3.3 70B Versatile (Recommended)'),
        ('deepseek-r1-distill-llama-70b', 'DeepSeek R1 Distill Llama 70B'),
        ('mixtral-8x7b-32768',            'Mixtral 8x7B 32K'),
        ('llama-3.1-8b-instant',          'Llama 3.1 8B Instant (Fast)'),
        ('gemma2-9b-it',                  'Gemma 2 9B IT'),
    ], string='Groq Model', default='llama-3.3-70b-versatile')

    # Claude model quick-select
    odex_ai_model_claude = fields.Selection([
        ('claude-sonnet-4-5',           'Claude Sonnet 4.5 (Latest — Recommended)'),
        ('claude-3-5-sonnet-20241022',  'Claude 3.5 Sonnet'),
        ('claude-3-5-haiku-20241022',   'Claude 3.5 Haiku (Fast)'),
        ('claude-3-opus-20240229',      'Claude 3 Opus (Most capable)'),
        ('claude-3-haiku-20240307',     'Claude 3 Haiku (Fastest)'),
    ], string='Claude Model', default='claude-sonnet-4-5')

    # OpenAI model quick-select
    odex_ai_model_openai = fields.Selection([
        ('gpt-4o',       'GPT-4o (Recommended)'),
        ('gpt-4o-mini',  'GPT-4o Mini (Fast & cheap)'),
        ('gpt-4-turbo',  'GPT-4 Turbo'),
        ('gpt-3.5-turbo','GPT-3.5 Turbo'),
    ], string='OpenAI Model', default='gpt-4o')

    # Gemini model quick-select
    odex_ai_model_gemini = fields.Selection([
        ('gemini-1.5-pro',       'Gemini 1.5 Pro'),
        ('gemini-1.5-flash',     'Gemini 1.5 Flash (Fast)'),
        ('gemini-2.0-flash-exp', 'Gemini 2.0 Flash (Experimental)'),
    ], string='Gemini Model', default='gemini-1.5-flash')

    # Ollama custom model name
    odex_ai_model_ollama = fields.Char(
        string='Ollama Model',
        default='llama3.2',
        help='Model name as shown in `ollama list` (e.g. llama3.2, mistral, codellama)',
    )

    # ── Generation parameters ─────────────────────────────────────────
    odex_ai_temperature = fields.Float(
        string='Temperature',
        config_parameter='odex_ai_assistant.temperature',
        default=0.7,
        help='Creativity level: 0.0 = deterministic, 1.0 = creative',
    )
    odex_ai_max_tokens = fields.Integer(
        string='Max Response Tokens',
        config_parameter='odex_ai_assistant.max_tokens',
        default=2048,
    )
    odex_ai_context_window = fields.Integer(
        string='Context Window (Messages)',
        config_parameter='odex_ai_assistant.context_window',
        default=20,
        help='How many previous messages to send as conversation context',
    )
    odex_ai_streaming_enabled = fields.Boolean(
        string='Enable Streaming Responses',
        config_parameter='odex_ai_assistant.streaming_enabled',
        default=True,
    )

    # ── System prompt / personality ───────────────────────────────────
    odex_ai_system_prompt = fields.Text(
        string='System Prompt',
        config_parameter='odex_ai_assistant.system_prompt',
        help='Custom instructions / personality for the AI assistant',
    )

    # ── Integration toggles ───────────────────────────────────────────
    odex_ai_enable_chatter = fields.Boolean(
        string='Enable Chatter Integration',
        config_parameter='odex_ai_assistant.enable_chatter',
        default=True,
    )
    odex_ai_enable_discuss = fields.Boolean(
        string='Enable Discuss Integration',
        config_parameter='odex_ai_assistant.enable_discuss',
        default=True,
    )
    odex_ai_notification_sound = fields.Boolean(
        string='Notification Sound',
        config_parameter='odex_ai_assistant.notification_sound',
        default=False,
    )

    # ── UI ────────────────────────────────────────────────────────────
    odex_ai_icon = fields.Selection([
        ('fa-robot',        '🤖 Robot'),
        ('fa-magic',        '✨ Magic Wand'),
        ('fa-bolt',         '⚡ Lightning'),
        ('fa-star',         '⭐ Star'),
        ('fa-brain',        '🧠 Brain'),
        ('fa-comment-dots', '💬 Chat'),
    ], string='AI Icon',
        config_parameter='odex_ai_assistant.ai_icon',
        default='fa-robot',
    )
    odex_ai_panel_position = fields.Selection([
        ('right',    'Right Sidebar'),
        ('left',     'Left Sidebar'),
        ('floating', 'Floating Window'),
    ], string='Panel Position',
        config_parameter='odex_ai_assistant.panel_position',
        default='right',
    )

    # ── Maintenance ───────────────────────────────────────────────────
    odex_ai_log_retention_days = fields.Integer(
        string='Log Retention (Days)',
        config_parameter='odex_ai_assistant.log_retention_days',
        default=90,
    )

    # ── Constraints ───────────────────────────────────────────────────
    @api.constrains('odex_ai_temperature')
    def _check_temperature(self):
        for rec in self:
            if not (0.0 <= rec.odex_ai_temperature <= 2.0):
                raise ValidationError(_('Temperature must be between 0.0 and 2.0'))

    @api.constrains('odex_ai_max_tokens')
    def _check_max_tokens(self):
        for rec in self:
            if not (100 <= rec.odex_ai_max_tokens <= 200000):
                raise ValidationError(_('Max tokens must be between 100 and 200,000'))

    # ── Onchange: sync model field ────────────────────────────────────
    @api.onchange('odex_ai_model_groq')
    def _onchange_model_groq(self):
        if self.odex_ai_provider == 'groq' and self.odex_ai_model_groq:
            self.odex_ai_model = self.odex_ai_model_groq

    @api.onchange('odex_ai_model_claude')
    def _onchange_model_claude(self):
        if self.odex_ai_provider == 'claude' and self.odex_ai_model_claude:
            self.odex_ai_model = self.odex_ai_model_claude

    @api.onchange('odex_ai_model_openai')
    def _onchange_model_openai(self):
        if self.odex_ai_provider == 'openai' and self.odex_ai_model_openai:
            self.odex_ai_model = self.odex_ai_model_openai

    @api.onchange('odex_ai_model_gemini')
    def _onchange_model_gemini(self):
        if self.odex_ai_provider == 'gemini' and self.odex_ai_model_gemini:
            self.odex_ai_model = self.odex_ai_model_gemini

    @api.onchange('odex_ai_model_ollama')
    def _onchange_model_ollama(self):
        if self.odex_ai_provider == 'ollama' and self.odex_ai_model_ollama:
            self.odex_ai_model = self.odex_ai_model_ollama

    @api.onchange('odex_ai_provider')
    def _onchange_provider(self):
        """Auto-select a sensible default model when the provider changes."""
        defaults = {
            'groq':   'llama-3.3-70b-versatile',
            'claude': 'claude-sonnet-4-5',
            'openai': 'gpt-4o',
            'gemini': 'gemini-1.5-flash',
            'ollama': 'llama3.2',
        }
        self.odex_ai_model = defaults.get(self.odex_ai_provider, '')

    # ── Frontend config getter ────────────────────────────────────────
    @api.model
    def get_ai_config(self):
        """Return current AI configuration for frontend use (no secrets)."""
        params = self.env['ir.config_parameter'].sudo()
        provider = params.get_param('odex_ai_assistant.provider', 'groq')

        # Determine which key is configured for the active provider
        key_params = {
            'groq':   'odex_ai_assistant.api_key',
            'claude': 'odex_ai_assistant.claude_api_key',
            'openai': 'odex_ai_assistant.openai_api_key',
            'gemini': 'odex_ai_assistant.gemini_api_key',
            'ollama': '',
        }
        key_param = key_params.get(provider, '')
        has_key = bool(params.get_param(key_param)) if key_param else True  # Ollama = always ready

        provider_labels = {
            'groq':   'Groq',
            'claude': 'Claude (Anthropic)',
            'openai': 'OpenAI',
            'gemini': 'Google Gemini',
            'ollama': 'Ollama (Local)',
        }

        return {
            'has_api_key':         has_key,
            'provider':            provider,
            'provider_label':      provider_labels.get(provider, provider),
            'model':               params.get_param('odex_ai_assistant.model', 'llama-3.3-70b-versatile'),
            'temperature':         float(params.get_param('odex_ai_assistant.temperature', '0.7')),
            'max_tokens':          int(params.get_param('odex_ai_assistant.max_tokens', '2048')),
            'streaming_enabled':   params.get_param('odex_ai_assistant.streaming_enabled', 'True') == 'True',
            'enable_chatter':      params.get_param('odex_ai_assistant.enable_chatter', 'True') == 'True',
            'enable_discuss':      params.get_param('odex_ai_assistant.enable_discuss', 'True') == 'True',
            'ai_icon':             params.get_param('odex_ai_assistant.ai_icon', 'fa-robot'),
            'panel_position':      params.get_param('odex_ai_assistant.panel_position', 'right'),
            'notification_sound':  params.get_param('odex_ai_assistant.notification_sound', 'False') == 'True',
            'context_window':      int(params.get_param('odex_ai_assistant.context_window', '20')),
        }
