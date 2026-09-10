# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AiMessage(models.Model):
    """
    Individual message within an AI conversation.
    Stores both user messages and AI responses.
    Linked to mail.message for Discuss integration.
    """
    _name = 'odex.ai.message'
    _description = 'AI Conversation Message'
    _order = 'create_date asc, id asc'

    conversation_id = fields.Many2one(
        'odex.ai.conversation',
        string='Conversation',
        required=True,
        ondelete='cascade',
        index=True,
    )
    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
    ], string='Role', required=True, default='user', index=True)
    content = fields.Text(string='Content', required=True)
    content_html = fields.Html(
        string='Rendered Content',
        compute='_compute_content_html',
        sanitize=True,
    )
    tokens_used = fields.Integer(string='Tokens Used', default=0)
    model_used = fields.Char(string='Model Used')
    # Link to mail.message for Discuss integration
    mail_message_id = fields.Many2one(
        'mail.message',
        string='Mail Message',
        ondelete='set null',
    )
    # Discuss channel message
    discuss_message_id = fields.Many2one(
        'mail.message',
        string='Discuss Message',
        ondelete='set null',
    )
    # Feedback
    feedback = fields.Selection([
        ('positive', 'Thumbs Up'),
        ('negative', 'Thumbs Down'),
        ('neutral', 'Neutral'),
    ], string='Feedback', default='neutral')
    # Metadata
    processing_time = fields.Float(string='Processing Time (s)', digits=(6, 3))
    is_error = fields.Boolean(string='Is Error', default=False)
    error_message = fields.Text(string='Error Details')
    user_id = fields.Many2one(
        'res.users',
        string='User',
        related='conversation_id.user_id',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='conversation_id.company_id',
        store=True,
        index=True,
    )

    @api.depends('content', 'role')
    def _compute_content_html(self):
        """Convert markdown-like content to safe HTML for display."""
        for rec in self:
            if rec.content:
                rec.content_html = rec.content
            else:
                rec.content_html = ''

    def action_copy_content(self):
        """Mark message as copied (for UI feedback)."""
        return True

    def action_feedback_positive(self):
        self.write({'feedback': 'positive'})

    def action_feedback_negative(self):
        self.write({'feedback': 'negative'})

    def post_to_chatter(self, record):
        """
        Post this AI message as a note in the record's chatter.
        Works with any model that has mail.thread mixin.
        """
        self.ensure_one()
        if not record or not hasattr(record, 'message_post'):
            return False
        try:
            body = f"<p><strong>🤖 ODEX AI Assistant:</strong></p>{self.content}"
            record.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                author_id=self.env.ref('base.partner_root').id,
            )
            return True
        except Exception as e:
            _logger.error("Failed to post AI message to chatter: %s", str(e))
            return False

    def post_to_discuss_channel(self, channel):
        """Post AI message to a Discuss channel."""
        self.ensure_one()
        if not channel:
            return False
        try:
            msg = channel.message_post(
                body=self.content,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=self.env.ref('base.partner_root').id,
            )
            self.write({'discuss_message_id': msg.id})
            return msg
        except Exception as e:
            _logger.error("Failed to post AI message to Discuss: %s", str(e))
            return False
