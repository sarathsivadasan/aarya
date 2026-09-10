import json
from odoo import models, _
from odoo.exceptions import UserError


class AIThread(models.Model):
    _inherit = 'ai.thread'

    def _get_tools_spec_chatgpt(self):
        """Build tools list for ChatGPT: function tools and optionally web search."""
        self.ensure_one()

        def _user_location():
            """Build user_location dict from current user or company address."""
            location = {}
            partner = self.env.user.partner_id
            if not partner.country_id and (company_partner := self.env.company.sudo().partner_id):
                partner = company_partner
            if partner.country_id:
                location['country'] = partner.country_id.code
            if partner.state_id:
                location['region'] = partner.state_id.name
            if partner.city:
                location['city'] = partner.city
            if self.env.user.tz:
                location['timezone'] = self.env.user.tz
            if location:
                location['type'] = 'approximate'
            return location

        tools_spec = [
            dict(type='function', **tool)
            for tool in self._get_tools_spec()
        ]
        if self.assistant_id.allow_web_search:
            web_search_tool = {"type": "web_search"}
            if location := _user_location():
                web_search_tool["user_location"] = location
            tools_spec.append(web_search_tool)
        return tools_spec

    def _do_request_chatgpt(self, message):
        """Handle ChatGPT API request"""
        self.ensure_one()
        config = self.sudo().config_id
        client = config._get_ai_client()

        params = {
            "model": config.model,
            "input": self._prepare_message_history_chatgpt(self.message_ids),
            "temperature": config.temperature,
            "max_output_tokens": config.max_tokens,
        }
        if thread_context := self._get_thread_context():
            params["instructions"] = thread_context
        if tools_spec := self._get_tools_spec_chatgpt():
            params["tools"] = tools_spec
            params["parallel_tool_calls"] = False

        try:
            return client.responses.create(**params)
        except Exception as e:
            raise UserError(_("ChatGPT API Error: %s") % str(e))

    def _prepare_message_history_chatgpt(self, messages):
        self.ensure_one()
        message_history = []
        for msg in messages:
            message_history.extend(msg._prepare_message_content_chatgpt())
        return message_history

    def _dump_response_json_chatgpt(self, response):
        self.ensure_one()
        response.instructions = None  # avoid storing large useless fields
        response.tools = []  # avoid storing large useless fields
        return response.model_dump_json(indent=2)

    def _parse_response_tool_chatgpt(self, response):
        for item in response.output:
            if item.type == 'function_call':
                return item.model_dump()
        return False

    def _execute_tool_chatgpt(self, func_call):
        func_name = func_call['name']
        arguments = json.loads(func_call['arguments'])
        return self._run_tool(func_name, **arguments)

    def _parse_response_text_chatgpt(self, response):
        """Parse ChatGPT response content"""
        return response.output_text
