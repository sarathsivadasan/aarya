import re

from odoo import _, api, models, fields
from odoo.exceptions import ValidationError
from odoo.tools.misc import remove_accents

_VALID_CODE_RE = re.compile(r'^[A-Za-z0-9-]+$')


class AIPromptTemplate(models.Model):
    _name = 'ai.prompt.template'
    _description = 'AI Prompt Template'
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    code = fields.Char(
        string="Code",
        compute='_compute_code',
        store=True,
        readonly=False,
        required=True,
    )
    template_content = fields.Text(string="Template Content", required=True)
    assistant_ids = fields.Many2many(
        'ai.assistant',
        relation='ai_assistant_prompt_template_rel',
        column1='template_id',
        column2='assistant_id',
        string="Assistants",
        help="Assistants that can use this template. If no assistant is assigned, "
             "the template will not appear in any chat.",
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Template code must be unique.'),
    ]

    @api.depends('name')
    def _compute_code(self):
        for rec in self:
            if rec.name:
                s = re.sub(r'[^a-z0-9-]+', '-', remove_accents(rec.name).lower())
                rec.code = s.strip('-') or 'template'
            else:
                rec.code = rec.code or ''

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not _VALID_CODE_RE.match(rec.code):
                raise ValidationError(_(
                    "Template code '%(code)s' is invalid. "
                    "Only letters, digits and hyphens are allowed.",
                    code=rec.code,
                ))

    @api.constrains('template_content')
    def _check_template_content(self):
        for rec in self:
            if '{prompt}' not in (rec.template_content or ''):
                raise ValidationError(_(
                    "Template '%(name)s' is missing the {prompt} marker.",
                    name=rec.name,
                ))

    def generate_prompt(self, prompt, **kwargs):
        self.ensure_one()
        try:
            return self.template_content.format(prompt=prompt, **kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required template argument: {e}")
