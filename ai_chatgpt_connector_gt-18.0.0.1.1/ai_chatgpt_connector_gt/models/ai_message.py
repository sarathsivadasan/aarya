import json
from openai.types.responses import Response as OpenAIResponse
from odoo import models
from odoo.addons.ai_base_gt.models.ai_thread import MESSAGE_TYPE_ROLE_MAP


class AIMessage(models.Model):
    _inherit = 'ai.message'

    def _filter_legit_attachments(self):
        # ChatGPT currently supports images and PDFs.
        if self.thread_id.sudo().config_id.type == 'chatgpt':
            return self.message_attachment_ids.filtered(
                lambda att: att.mimetype.startswith('image/') or att.mimetype == 'application/pdf'
            )
        return super()._filter_legit_attachments()

    def _prepare_message_content_chatgpt(self):
        self.ensure_one()

        if self.response:
            response = OpenAIResponse.model_validate_json(self.response)
            return [output.model_dump(exclude_none=True) for output in response.output]

        content = {
            'role': MESSAGE_TYPE_ROLE_MAP[self.message_type],
            'content': [],
        }

        if self.content:
            content["content"].append({
                "type": "input_text",
                "text": self.content_full
            })

        if self.func_result:
            prev_message = self.thread_id.message_ids.filtered(lambda m: m.id < self.id)[-1:]
            func_call = json.loads(prev_message.func_call or "{}")
            content = {
                "type": "function_call_output",
                "call_id": func_call['call_id'],
                "output": self.func_result
            }
        # Keep for backward compatibility
        elif self.func_call:
            func_call = json.loads(self.func_call)
            # Convert function call structure from Chat Completion API to Response API
            if func_call['type'] == 'function':
                content = {
                    "type": "function_call",
                    "call_id": func_call['id'],
                    "name": func_call['function']['name'],
                    "arguments": func_call['function']['arguments']
                }
            else:
                content = func_call
        # End of backward compatibility

        contents = [content]

        att_contents = []
        for attachment in self.legit_attachment_ids:
            if attachment.mimetype.startswith('image/'):
                att_contents.append({
                    "type": "input_image",
                    "image_url": f"data:{attachment.mimetype};base64,{attachment.datas.decode('utf-8')}"
                })
            else:
                att_contents.append({
                    "type": "input_file",
                    "filename": attachment.name,
                    "file_data": f"data:{attachment.mimetype};base64,{attachment.datas.decode('utf-8')}"
                })
        if att_contents:
            if 'content' in content:
                content['content'].extend(att_contents)
            else:
                contents.append({
                    'role': 'user',  # must use 'user' role because others does not allow files
                    'content': att_contents
                })

        return contents
