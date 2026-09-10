# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AiFeedback(models.Model):
    """Collects user feedback on AI responses for quality improvement."""
    _name = 'odex.ai.feedback'
    _description = 'AI Response Feedback'
    _order = 'create_date desc'

    message_id = fields.Many2one(
        'odex.ai.message',
        string='AI Message',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
    )
    rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Rating')
    feedback_type = fields.Selection([
        ('positive', 'Helpful'),
        ('negative', 'Not Helpful'),
        ('incorrect', 'Incorrect'),
        ('incomplete', 'Incomplete'),
        ('other', 'Other'),
    ], string='Feedback Type', required=True)
    comment = fields.Text(string='Comment')
    company_id = fields.Many2one(
        'res.company',
        related='message_id.company_id',
        store=True,
    )
