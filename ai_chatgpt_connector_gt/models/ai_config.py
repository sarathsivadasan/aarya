from openai import OpenAI
from odoo import fields, models, _
from odoo.exceptions import UserError


class AIConfig(models.Model):
    _inherit = 'ai.config'

    type = fields.Selection(
        selection_add=[('chatgpt', 'ChatGPT')],
        ondelete={'chatgpt': 'cascade'}
    )

    def _compute_allow_web_search(self):
        super()._compute_allow_web_search()
        for r in self:
            if r.type == 'chatgpt':
                r.allow_web_search = True

    def _get_default_model(self):
        if self.type == 'chatgpt':
            return 'gpt-5-mini'
        return super()._get_default_model()

    def _get_chatgpt_client(self):
        if not self.api_key:
            raise UserError(_("ChatGPT API key is not configured"))
        return OpenAI(api_key=self.api_key)
