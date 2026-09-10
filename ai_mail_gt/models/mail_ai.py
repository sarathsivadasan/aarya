import logging
import re
import traceback
from markdownify import markdownify
from markupsafe import Markup
from odoo import models
from odoo.tools import ormcache
from odoo.addons.ai_base_gt.models.tools import after_commit

_logger = logging.getLogger(__name__)


class MailAI(models.AbstractModel):
    _name = 'mail.ai'
    _description = 'Mail AI'

    @ormcache()
    def _get_ai_partner_ids(self):
        return self.env['res.partner'].sudo().with_context(active_test=False).search([
            ('is_ai', '=', True)
        ]).ids

    def _get_ai_threads_by_partner_ids(self, record, ai_partner_ids):
        AIThread = self.env['ai.thread']
        Partner = self.env['res.partner']
        threads = AIThread.search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('ai_partner_id', 'in', ai_partner_ids),
        ])
        if missing_ids := (set(ai_partner_ids) - set(threads.ai_partner_id.ids)):
            for missing_id in missing_ids:
                assistant = Partner.sudo().browse(missing_id).ai_assistant_ids[:1]
                threads |= AIThread.create({
                    'name': record.display_name,
                    'assistant_id': assistant.id,
                    'res_model': record._name,
                    'res_id': record.id,
                })
        return threads

    def _can_use_prompt_template(self):
        return self.env.user._is_internal()

    def _parse_prompt_template(self, prompt, thread):
        """Parse %code prefix from prompt and resolve the template against the thread's assistant.

        Returns (remainder, template_id) if a valid template is found,
        otherwise (prompt, None) leaving the prompt unchanged.
        """
        if not self._can_use_prompt_template():
            return prompt, None
        template_ids = thread.assistant_id.prompt_template_ids.ids
        if not template_ids:
            return prompt, None
        match = re.match(r'^%([A-Za-z0-9-]+)\s*(.*)', prompt, re.DOTALL)
        if not match:
            return prompt, None
        template_name, remainder = match.group(1), match.group(2).strip()
        template = self.env['ai.prompt.template'].search(
            [('code', '=ilike', template_name), ('id', 'in', template_ids)], limit=1
        )
        if not template:
            return prompt, None
        return remainder, template.id

    def _apply_logic(self, record, message, values):
        if len(record) != 1 or values.get("author_id") in self._get_ai_partner_ids() or values.get("message_type") != "comment":
            return
        if ai_partner_ids := (self._is_ai_pinged(values) or self._is_ai_in_private_channel(record)):
            raw_prompt = markdownify(message.body.replace(u'\xa0', u' ').strip())
            ai_threads = self._get_ai_threads_by_partner_ids(record, ai_partner_ids)
            for thread in ai_threads:
                prompt, template_id = self._parse_prompt_template(raw_prompt, thread)
                context = {
                    'mail_thread_model': record._name,
                    'mail_thread_id': record.id,
                    'mail_message_id': message.id,
                }
                prompt_message = thread.with_context(**context)._create_prompt_message(prompt, template_id, msg_vals=values)
                self.with_context(**context)._ai_request_after_commit(thread.id, prompt, prompt_message.id, values)

    @after_commit(wait=True)
    def _ai_request_after_commit(self, thread_id, prompt, prompt_message_id=None, values=None):
        thread = self.env['ai.thread'].browse(thread_id)
        values = values or {}
        try:
            thread._send_request(prompt, prompt_message_id, msg_vals=values)
        except Exception as e:
            _logger.error(traceback.format_exc())
            self.env.cr.rollback()
            err_msg = e.args[0].replace('\n', '<br/>')
            error_html = Markup(f'<div class="alert alert-danger" role="alert">{err_msg}</div>')
            record = self.env[thread.res_model].browse(thread.res_id)
            default_message_type = 'comment'
            default_subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_comment')
            record.with_user(thread.ai_user_id).with_context(
                mail_create_nosubscribe=True
            ).sudo().message_post(
                body=error_html,
                author_id=thread.ai_partner_id.id,
                message_type=values.get('message_type', default_message_type),
                subtype_id=values.get('subtype_id', default_subtype_id),
                partner_ids=self.env.user.partner_id.ids,
            )

    def _is_ai_pinged(self, values):
        ai_partner_ids = self._get_ai_partner_ids()
        return list(set(ai_partner_ids) & set(values.get('partner_ids', [])))

    def _is_ai_in_private_channel(self, record):
        ai_partner_ids = self._get_ai_partner_ids()
        if record._name == 'discuss.channel' and record.channel_type in ('chat', 'ai_chat'):
            return list(set(ai_partner_ids) & set(record.with_context(active_test=False).channel_partner_ids.ids))
        return False
