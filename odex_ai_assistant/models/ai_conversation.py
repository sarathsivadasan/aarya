# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class AiConversation(models.Model):
    """
    Represents a single AI conversation session.
    Each session contains multiple messages and belongs to one user.
    Supports multi-company architecture.
    """
    _name = 'odex.ai.conversation'
    _description = 'AI Conversation Session'
    _order = 'write_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Conversation Title',
        required=True,
        default=lambda self: _('New Conversation'),
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    message_ids = fields.One2many(
        'odex.ai.message',
        'conversation_id',
        string='Messages',
    )
    message_count = fields.Integer(
        string='Message Count',
        compute='_compute_message_count',
        store=True,
    )
    state = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('pinned', 'Pinned'),
    ], string='State', default='active', index=True)
    is_pinned = fields.Boolean(string='Pinned', default=False, index=True)
    # Context tracking - which record this conversation relates to
    res_model = fields.Char(string='Related Model', index=True)
    res_id = fields.Integer(string='Related Record ID', index=True)
    res_name = fields.Char(string='Related Record Name')
    # Discuss channel link
    discuss_channel_id = fields.Many2one(
        'discuss.channel',
        string='Discuss Channel',
        ondelete='set null',
    )
    # Summary and metadata
    summary = fields.Text(string='Auto Summary')
    total_tokens = fields.Integer(string='Total Tokens Used', default=0)
    last_message_date = fields.Datetime(string='Last Message', index=True)
    color = fields.Integer(string='Color Index', default=0)
    tag_ids = fields.Many2many(
        'odex.ai.conversation.tag',
        'ai_conversation_tag_rel',
        'conversation_id',
        'tag_id',
        string='Tags',
    )
    active = fields.Boolean(default=True, index=True)

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    def action_archive(self):
        self.write({'state': 'archived', 'active': False})

    def action_pin(self):
        self.write({'is_pinned': True, 'state': 'pinned'})

    def action_unpin(self):
        self.write({'is_pinned': False, 'state': 'active'})

    def action_clear_messages(self):
        self.message_ids.unlink()
        self.write({'summary': False, 'total_tokens': 0, 'last_message_date': False})

    def get_conversation_context(self, limit=20):
        """
        Returns the last N messages formatted for the AI API.
        Used to maintain conversation memory/context.
        """
        self.ensure_one()
        messages = self.message_ids.search([
            ('conversation_id', '=', self.id),
        ], order='create_date asc', limit=limit)
        context = []
        for msg in messages:
            context.append({
                'role': msg.role,
                'content': msg.content,
            })
        return context

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.res_name:
                name = f"{rec.name} [{rec.res_name}]"
            result.append((rec.id, name))
        return result

    @api.model
    def get_or_create_session(self, res_model=None, res_id=None):
        """Get active session for current user or create a new one."""
        domain = [
            ('user_id', '=', self.env.user.id),
            ('state', 'in', ['active', 'pinned']),
            ('company_id', '=', self.env.company.id),
        ]
        if res_model and res_id:
            domain += [('res_model', '=', res_model), ('res_id', '=', res_id)]

        session = self.search(domain, order='write_date desc', limit=1)
        if not session:
            vals = {
                'name': _('New Conversation'),
                'user_id': self.env.user.id,
                'company_id': self.env.company.id,
            }
            if res_model and res_id:
                vals['res_model'] = res_model
                vals['res_id'] = res_id
                try:
                    record = self.env[res_model].browse(res_id)
                    vals['res_name'] = record.display_name
                except Exception:
                    pass
            session = self.create(vals)
        return session


class AiConversationTag(models.Model):
    """Tags for organizing AI conversations."""
    _name = 'odex.ai.conversation.tag'
    _description = 'AI Conversation Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index', default=0)
