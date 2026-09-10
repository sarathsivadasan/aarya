from ast import literal_eval
from odoo import models, api


class AIAssistant(models.Model):
    _inherit = 'ai.assistant'

    @api.model
    def get_assistants_for_record(self, res_model, res_id):
        """
        Get assistants that can access the record.
        """
        record = self.env[res_model].browse(res_id)
        assistants = self.browse()

        # Super assistants
        if super_assistants := self.search([('is_super_assistant', '=', True)]):
            assistants |= super_assistants

        # Assistants with data sources that can access the record
        data_sources = self.env['ai.data.source'].browse()
        for data_source in self.env['ai.data.source'].search([('type', '=', 'model'), ('model', '=', res_model)]):
            model_domain = data_source.model_domain and literal_eval(data_source.model_domain) or []
            if not model_domain or record.filtered_domain(model_domain):
                data_sources |= data_source
        if data_sources:
            assistants |= self.search([('assistant_data_source_ids.data_source_id', 'in', data_sources.ids)])

        result = []
        for assistant in assistants.sorted():
            result.append({
                'id': assistant.id,
                'name': assistant.name,
                'description': assistant.description,
                'partner_id': assistant.partner_id.id,
            })
        return result
