# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-install hook to set up initial AI assistant data."""
    _logger.info("ODEX AI Assistant: Running post-install hook...")

    # Create default AI Discuss channel if not exists
    try:
        channel = env['discuss.channel'].sudo().search([
            ('name', '=', 'AI Assistant'),
            ('channel_type', '=', 'channel'),
        ], limit=1)

        if not channel:
            channel = env['discuss.channel'].sudo().create({
                'name': 'AI Assistant',
                'channel_type': 'channel',
                'description': 'ODEX AI Assistant - Your intelligent Odoo companion',
            })
            _logger.info("ODEX AI Assistant: Created default AI Discuss channel (ID: %s)", channel.id)
    except Exception as e:
        _logger.warning("ODEX AI Assistant: Could not create default channel: %s", str(e))

    # Set default config parameters
    config_params = env['ir.config_parameter'].sudo()
    defaults = {
        'odex_ai_assistant.model': 'llama-3.3-70b-versatile',
        'odex_ai_assistant.temperature': '0.7',
        'odex_ai_assistant.max_tokens': '2048',
        'odex_ai_assistant.streaming_enabled': 'True',
        'odex_ai_assistant.system_prompt': (
            "You are ODEX AI Assistant, an intelligent assistant integrated into Odoo ERP. "
            "You help users with business operations, data analysis, report generation, "
            "and smart recommendations. You have deep knowledge of Odoo modules including "
            "Sales, Purchase, Inventory, Accounting, CRM, Manufacturing, Fleet/Vehicle "
            "Management, and Workshop operations. Always provide concise, actionable responses "
            "in the context of the user's current workflow."
        ),
    }
    for key, value in defaults.items():
        if not config_params.get_param(key):
            config_params.set_param(key, value)

    _logger.info("ODEX AI Assistant: Post-install hook completed successfully.")


def uninstall_hook(env):
    """Cleanup hook on uninstall."""
    _logger.info("ODEX AI Assistant: Running uninstall hook...")
    try:
        channel = env['discuss.channel'].sudo().search([
            ('name', '=', 'AI Assistant'),
        ], limit=1)
        if channel:
            channel.sudo().unlink()
    except Exception as e:
        _logger.warning("ODEX AI Assistant: Uninstall cleanup error: %s", str(e))
