# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AiSmartAction(models.Model):
    """
    Quick AI actions that appear contextually on forms/views.
    Can be model-specific or global.
    """
    _name = 'odex.ai.smart.action'
    _description = 'AI Smart Action'
    _order = 'sequence, name'

    name = fields.Char(string='Action Name', required=True)
    sequence = fields.Integer(default=10)
    description = fields.Char(string='Tooltip Description')
    icon = fields.Char(string='Icon Class', default='fa-bolt')
    color = fields.Char(string='Button Color', default='#875A7B')
    # The prompt that will be sent to AI when this action is triggered
    action_prompt = fields.Text(
        string='AI Prompt',
        required=True,
        help="Use {record_data} for current record JSON, "
             "{model_name} for model display name.",
    )
    # Where this action appears
    target_model = fields.Char(
        string='Target Model',
        help="Leave blank for all models. Use technical name e.g. sale.order",
        index=True,
    )
    view_type = fields.Selection([
        ('form', 'Form View'),
        ('list', 'List View'),
        ('kanban', 'Kanban View'),
        ('all', 'All Views'),
    ], string='Available In', default='form')
    # What happens with the AI response
    action_type = fields.Selection([
        ('show_popup', 'Show in AI Panel'),
        ('post_chatter', 'Post to Chatter'),
        ('create_note', 'Create Internal Note'),
        ('create_activity', 'Create Activity'),
        ('copy_clipboard', 'Copy to Clipboard'),
    ], string='Response Action', default='show_popup')
    active = fields.Boolean(default=True)
    is_system = fields.Boolean(default=False)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    @api.model
    def get_actions_for_model(self, model_name, view_type='form'):
        """Return smart actions available for a given model and view type."""
        domain = [
            ('active', '=', True),
            '|',
            ('target_model', '=', False),
            ('target_model', '=', model_name),
            '|',
            ('view_type', '=', 'all'),
            ('view_type', '=', view_type),
        ]
        actions = self.search(domain, order='sequence, name')
        return actions.read(['id', 'name', 'description', 'icon', 'color', 'action_prompt', 'action_type'])
