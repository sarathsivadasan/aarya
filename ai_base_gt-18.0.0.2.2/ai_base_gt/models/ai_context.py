from odoo import fields, models


class AIContext(models.Model):
    _name = 'ai.context'
    _description = "AI Context"

    name = fields.Char(string="Name", required=True)
    apply_mode = fields.Selection([
        ('always', 'Always'),
        ('flexible', 'Flexible'),
    ], string="Apply Mode", default='always', required=True,
        help="Always: full content injected into every system prompt.\n"
             "Flexible: only the title and ID are listed; the AI loads full content "
             "on demand via _load_context when the user's request is relevant.")
    context = fields.Text(string="Context", required=True)
