import logging
from typing import Optional
from markupsafe import Markup

from odoo import models, fields, api, Command, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.addons.ai_base_gt.models.ai_thread import ai_tool
from odoo.addons.mail.tools.discuss import Store

_logger = logging.getLogger(__name__)


def parse_m2m(commands):
    "Return a list of ids corresponding to a many2many value"
    ids = []
    for command in commands:
        if isinstance(command, (tuple, list)):
            if command[0] in (Command.UPDATE, Command.LINK):
                ids.append(command[1])
            elif command[0] == Command.CLEAR:
                ids = []
            elif command[0] == Command.SET:
                ids = list(command[2])
        else:
            ids.append(command)
    return ids


class AIThread(models.Model):
    _inherit = 'ai.thread'

    discuss_channel_id = fields.Many2one('discuss.channel', string='Discuss Channel',
                                         compute='_compute_discuss_channel_id', store=True)

    @api.depends('res_model', 'res_id')
    def _compute_discuss_channel_id(self):
        res_ids = self.filtered(lambda r: r.res_model == 'discuss.channel').mapped('res_id')
        channels = self.env['discuss.channel'].search([('id', 'in', res_ids)])
        channel_ids = set(channels.ids)
        for r in self:
            if r.res_model == 'discuss.channel':
                r.discuss_channel_id = r.res_id in channel_ids and r.res_id or False
            else:
                r.discuss_channel_id = False

    def _get_attachments_to_request(self, kwargs):
        attachments = super()._get_attachments_to_request(kwargs)
        if 'attachments' not in kwargs:
            attachment_ids = parse_m2m(kwargs.get('msg_vals', {}).get('attachment_ids', []))
            if attachment_ids:
                attachments = self.env['ir.attachment'].browse(attachment_ids).exists()
        return attachments

    @api.model
    def get_model_suggestions(self, term, thread_id, limit=8):
        """
        Get model suggestions for $ pattern
        Returns models that match the search term and that the user has read access to
        """
        Model = self.env['ir.model'].sudo()
        allowed_models = self.env['ir.model.access']._get_allowed_models('read')
        args = [('model', 'in', list(allowed_models))]
        model_ids = [r[0] for r in Model.name_search(term or '', args=args, limit=limit)]
        models = Model.browse(model_ids)
        return [{
            'id': model.id,
            'model': model.model,
            'name': model.name,
            'label': model.model,
        } for model in models]

    @api.model
    def get_record_suggestions(self, model, record_term, thread_id, limit=8):
        """
        Get record suggestions for $model/ pattern
        Returns records from specified model that match the search term
        """
        try:
            Model = self.env[model]
            name_search_results = Model.name_search(record_term, limit=limit)
            ids = [r[0] for r in name_search_results]
            records = Model.browse(ids)
            return [{
                'id': record.id,
                'model': model,
                'name': record.display_name,
                'label': f"{model}/{record.id}",
                'url': f'/mail/view?model={model}&res_id={record.id}',
                'write_date': fields.Datetime.to_string(record.write_date),
            } for record in records]
        except Exception:
            return []

    def _format_tool_record_values(self, model_name: str, values: list[dict]) -> list[dict]:
        results = super()._format_tool_record_values(model_name, values)
        base_url = self.get_base_url()
        for value, result in zip(values, results):
            result['url'] = f"{base_url}/mail/view?model={model_name}&res_id={value['id']}"
        return results

    def _clean_context(self):
        _self = super()._clean_context()
        # Remove mail_thread_model, mail_thread_id, mail_message_id from context to avoid unexpected behavior
        # in AI tools called from non-mail context (e.g. cron, automated action) or from another mail thread.
        _context = dict(_self.env.context)
        for key in ('mail_thread_model', 'mail_thread_id', 'mail_message_id'):
            _context.pop(key, None)
        return _self.with_context(_context)

    @ai_tool(
        condition=lambda thread: thread.assistant_id.has_model_read_access,
        typing_indicator='Reading conversation...',
    )
    def _read_thread_conversation(self, thread_model: str, thread_id: int, limit: int = 10, offset: int = 0) -> dict:
        """
        Read the conversation of a thread in Odoo. The returned messages are sorted from the newest to the oldest.

        Args:
            thread_model (str): The technical name of the thread model.
            thread_id (int): The ID of the thread to retrieve.
            limit (int, optional): The maximum number of the messages to return. Default is 10.
            offset (int, optional): The number of messages to skip from the newest messages. Default is 0.

        Returns:
            dict:
                - total_messages (int): The total number of messages in the thread.
                - limit (int): The limit value provided.
                - offset (int): The offset value provided.
                - messages (list): The list of formatted messages, sorted from the newest to the oldest.
        """
        self.ensure_one()
        if not any(getattr(cls, '_name', None) == 'mail.thread' for cls in self.env.registry[thread_model].mro()):
            raise UserError("Model %s is not a thread model." % thread_model)
        self.assistant_id._check_model_fields_access(thread_model, 'read', ['message_ids'])
        domain = expression.AND([[('id', '=', thread_id)], self.assistant_id._get_model_domain_access(thread_model, 'read')])
        thread = self.env[thread_model].search(domain, limit=1)
        if not thread:
            raise UserError("Thread with id %s in model %s does not exist or cannot be accessed." % (thread_id, thread_model))
        total_messages = len(thread.message_ids)
        messages = thread.message_ids.sorted()[offset:offset+limit]
        return {
            'total_messages': total_messages,
            'limit': limit,
            'offset': offset,
            'messages': Store(messages, for_current_user=True).get_result()
        }

    @ai_tool(
        condition=lambda thread: thread.assistant_id.has_model_write_access,
        typing_indicator='Posting message...',
    )
    def _post_message_to_thread(self, thread_model: str, thread_id: int, body: str,
                                subject: Optional[str] = None, message_type: str = 'comment',
                                subtype_xmlid: str = 'mail.mt_comment', partner_ids: Optional[list[int]] = None,
                                attachment_ids: Optional[list[int]] = None) -> dict:
        """
        Post a message to a mail.thread record (chatter). Use this to send a comment, or an
        internal note on leads, tasks, channels, etc.

        **Choosing subtype_xmlid (important):**
        - Use **mail.mt_note** when the user asks to "post a note", "add an internal note",
          "log a note", "internal note", or "private note". Notes are internal only and
          are not shown to customers / external followers as a visible comment.
        - Use **mail.mt_comment** when the user asks to "post a comment", "send a message",
          "notify", or when the message should be visible to followers (e.g. a visible
          chatter message). Do NOT use mail.mt_comment for "post a note" or "internal note".

        Args:
            thread_model (str): Technical name of the thread model (e.g. 'crm.lead', 'project.task', 'discuss.channel').
            thread_id (int): ID of the record to post to.
            body (str): Message body, must be in HTML.
            subject (str, optional): Subject; omit if not needed.
            message_type (str, optional): 'comment', 'email', etc. Default 'comment'.
            subtype_xmlid (str, optional): 'mail.mt_note' = internal note; 'mail.mt_comment' = visible comment. Default 'mail.mt_comment'.
            partner_ids (list[int], optional): Partner IDs to notify.
            attachment_ids (list[int], optional): Attachment IDs to attach.

        Returns:
            dict: message_id (int).
        """
        self.ensure_one()
        # Check model access through assistant (write: posting message)
        self.assistant_id._check_model_fields_access(thread_model, 'write', ['message_ids'])

        # Find thread
        Model = self.env[thread_model]
        domain = expression.AND([[('id', '=', thread_id)], self.assistant_id._get_model_domain_access(thread_model, 'write')])
        thread = Model.search(domain, limit=1)
        if not thread:
            raise UserError("Thread with id %s in model %s does not exist or cannot be accessed." % (thread_id, thread_model))

        # Prepare message_post parameters
        msg_kwargs = {
            'body': Markup(body),
            'message_type': message_type,
            'author_id': self.ai_partner_id.id,
        }
        if subject:
            msg_kwargs['subject'] = subject
        if subtype_xmlid:
            msg_kwargs['subtype_xmlid'] = subtype_xmlid
        if partner_ids:
            msg_kwargs['partner_ids'] = partner_ids
        if attachment_ids:
            msg_kwargs['attachment_ids'] = attachment_ids

        # Post the message
        message = thread.message_post(**msg_kwargs)
        return {'message_id': message.id}

    # -------------------------------------------------------------------------
    # Typing indicator
    # -------------------------------------------------------------------------

    def _send_request(self, prompt, prompt_message_id=None, template_id=None, **kwargs):
        self._send_typing_indicator(True, 'Thinking...')
        try:
            return super()._send_request(prompt, prompt_message_id, template_id, **kwargs)
        finally:
            self._send_typing_indicator(False)

    def _run_tool(self, tool_name, **kwargs):
        method = getattr(self, tool_name, None)
        msg = getattr(method, 'ai_typing_indicator', None) or 'Processing...'
        self._send_typing_indicator(True, msg)
        return super()._run_tool(tool_name, **kwargs)

    def _send_typing_indicator(self, is_typing, status_text=''):
        ctx = self.env.context
        if ctx.get('mail_thread_model') != 'discuss.channel':
            return
        channel_id = ctx.get('mail_thread_id')
        if not channel_id:
            return
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                channel = env['discuss.channel'].browse(channel_id)
                env['bus.bus']._sendone(
                    channel,
                    'ai_mail_gt/ai_typing_status',
                    {
                        'channel_id': channel_id,
                        'partner_id': self.assistant_id.partner_id.id,
                        'is_typing': is_typing,
                        'status_text': status_text,
                    }
                )
        except Exception:
            _logger.warning('Failed to send AI typing indicator', exc_info=True)
