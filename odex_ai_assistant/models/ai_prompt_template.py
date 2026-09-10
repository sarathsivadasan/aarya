# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AiPromptTemplate(models.Model):
    """
    Reusable prompt templates for common AI tasks.
    Can be scoped to specific Odoo models for context-aware suggestions.
    """
    _name = 'odex.ai.prompt.template'
    _description = 'AI Prompt Template'
    _order = 'sequence, name'

    name = fields.Char(string='Template Name', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    category = fields.Selection([
        ('general', 'General'),
        ('crm', 'CRM / Sales'),
        ('accounting', 'Accounting'),
        ('purchase', 'Purchase'),
        ('inventory', 'Inventory'),
        ('vehicle', 'Vehicle Management'),
        ('job_card', 'Job Card / Workshop'),
        ('inspection', 'Vehicle Inspection'),
        ('spare_parts', 'Spare Parts'),
        ('workshop', 'Workshop Operations'),
        ('hr', 'Human Resources'),
        ('project', 'Project Management'),
        ('custom', 'Custom'),
    ], string='Category', required=True, default='general', index=True)
    prompt_text = fields.Text(
        string='Prompt Template',
        required=True,
        help="Use {record_data} for current record context, {user_name} for current user, "
             "{company_name} for company name.",
    )
    description = fields.Char(string='Short Description')
    icon = fields.Char(string='Icon', default='fa-magic', help="Font Awesome icon class")
    # Model restriction - if set, template only shows for this model
    applicable_model = fields.Char(
        string='Applicable Model',
        index=True,
        help="Technical name of the model (e.g. sale.order). Leave empty for global templates.",
    )
    is_system = fields.Boolean(
        string='System Template',
        default=False,
        help="System templates cannot be deleted by users.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
    )
    use_count = fields.Integer(string='Times Used', default=0)

    @api.model
    def get_templates_for_model(self, model_name=None):
        """
        Return templates applicable to the given model.
        Returns global templates + model-specific templates.
        """
        domain = [('active', '=', True)]
        if model_name:
            domain = ['|',
                ('applicable_model', '=', False),
                ('applicable_model', '=', model_name),
            ]
        templates = self.search(domain, order='sequence, name')
        return templates.read(['id', 'name', 'prompt_text', 'category', 'icon', 'description'])

    def action_increment_use_count(self):
        self.sudo().write({'use_count': self.use_count + 1})

    def get_formatted_prompt(self, record_data=None, user_name=None, company_name=None):
        """Format the prompt template with context variables."""
        self.ensure_one()
        prompt = self.prompt_text
        try:
            prompt = prompt.replace('{record_data}', str(record_data or ''))
            prompt = prompt.replace('{user_name}', user_name or self.env.user.name)
            prompt = prompt.replace('{company_name}', company_name or self.env.company.name)
        except Exception:
            pass
        return prompt
