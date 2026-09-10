from odoo import api, models
from odoo.osv import expression


class AIPromptTemplate(models.Model):
    _inherit = 'ai.prompt.template'

    @api.model
    def get_suggestions(self, term='', assistant_id=None, channel_id=None):
        if not self.env.user._is_internal():
            return []

        if not assistant_id and channel_id:
            channel = self.env['discuss.channel'].browse(channel_id)
            partner_ids = channel.sudo().with_context(active_test=False).channel_partner_ids.ids
            assistant = self.env['ai.assistant'].search(
                [('partner_id', 'in', partner_ids)], limit=1
            )
            assistant_id = assistant.id if assistant else None

        if not assistant_id:
            return []

        assistant = self.env['ai.assistant'].search([('id', '=', assistant_id)], limit=1)
        if not assistant:
            return []
        template_ids = assistant.prompt_template_ids.ids
        if not template_ids:
            return []

        domain = [('id', 'in', template_ids)]
        if term:
            domain = expression.AND([
                domain, ['|', ('name', 'ilike', term), ('code', 'ilike', term)]
            ])

        templates = self.search(domain, limit=20, order='sequence, id')
        return [
            {
                'id': t.id,
                'name': t.name,
                'code': t.code,
                'preview': t.template_content[:80].replace('\n', ' '),
            }
            for t in templates
        ]
