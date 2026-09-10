# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta


class AiUsageLog(models.Model):
    """
    Tracks all AI API requests for analytics, billing awareness,
    and debugging purposes.
    """
    _name = 'odex.ai.usage.log'
    _description = 'AI Usage Log'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='User', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    conversation_id = fields.Many2one(
        'odex.ai.conversation',
        string='Conversation',
        ondelete='set null',
        index=True,
    )
    model_used = fields.Char(string='AI Model', required=True, index=True)
    prompt_tokens = fields.Integer(string='Prompt Tokens', default=0)
    completion_tokens = fields.Integer(string='Completion Tokens', default=0)
    total_tokens = fields.Integer(
        string='Total Tokens',
        compute='_compute_total_tokens',
        store=True,
    )
    processing_time = fields.Float(string='Processing Time (s)', digits=(6, 3))
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('rate_limited', 'Rate Limited'),
    ], string='Status', required=True, default='success', index=True)
    error_message = fields.Text(string='Error Message')
    res_model = fields.Char(string='Source Model', index=True)
    res_id = fields.Integer(string='Source Record ID')
    request_type = fields.Selection([
        ('chat', 'Chat Message'),
        ('summary', 'Record Summary'),
        ('chatter', 'Chatter Action'),
        ('template', 'Template Action'),
        ('context', 'Context Analysis'),
    ], string='Request Type', default='chat', index=True)

    @api.depends('prompt_tokens', 'completion_tokens')
    def _compute_total_tokens(self):
        for rec in self:
            rec.total_tokens = rec.prompt_tokens + rec.completion_tokens

    @api.model
    def get_usage_stats(self, days=30):
        """Return usage statistics for the last N days."""
        date_from = datetime.now() - timedelta(days=days)
        domain = [
            ('create_date', '>=', date_from),
            ('company_id', '=', self.env.company.id),
        ]
        logs = self.search(domain)
        if not logs:
            return {
                'total_requests': 0,
                'total_tokens': 0,
                'success_rate': 0,
                'avg_response_time': 0,
            }
        total = len(logs)
        successful = logs.filtered(lambda l: l.status == 'success')
        return {
            'total_requests': total,
            'total_tokens': sum(logs.mapped('total_tokens')),
            'success_rate': round((len(successful) / total) * 100, 1) if total else 0,
            'avg_response_time': round(
                sum(logs.mapped('processing_time')) / total if total else 0, 3
            ),
            'by_model': self._get_by_model(logs),
            'by_user': self._get_by_user(logs),
        }

    def _get_by_model(self, logs):
        result = {}
        for log in logs:
            model = log.model_used or 'unknown'
            if model not in result:
                result[model] = {'count': 0, 'tokens': 0}
            result[model]['count'] += 1
            result[model]['tokens'] += log.total_tokens
        return result

    def _get_by_user(self, logs):
        result = {}
        for log in logs:
            user = log.user_id.name or 'Unknown'
            if user not in result:
                result[user] = {'count': 0, 'tokens': 0}
            result[user]['count'] += 1
            result[user]['tokens'] += log.total_tokens
        return result

    @api.model
    def cleanup_old_logs(self, days=90):
        """Remove logs older than specified days. Called by cron job."""
        cutoff = datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        old_logs.unlink()
        return count
