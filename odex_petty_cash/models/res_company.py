# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompanyPettyCash(models.Model):
    _inherit = 'res.company'

    # Journal
    petty_cash_journal_id = fields.Many2one(
        'account.journal', string='Default Petty Cash Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
    )
    # GL Accounts
    petty_cash_gl_account_id = fields.Many2one(
        'account.account', string='Petty Cash GL Account (Asset)',
        domain=[('deprecated', '=', False)],
        help="Asset account representing petty cash. DR on allocation, CR on expense.",
    )
    cash_receipt_account_id = fields.Many2one(
        'account.account', string='Cash Receipt Credit Account',
        domain=[('deprecated', '=', False)],
        help="Credited when cash is issued to a user (Allocation). Typically Cash/Bank.",
    )
    cash_expense_account_id = fields.Many2one(
        'account.account', string='Default Cash Expense Account',
        domain=[('deprecated', '=', False)],
        help="Fallback expense GL when a category has no account mapped.",
    )
    cash_return_account_id = fields.Many2one(
        'account.account', string='Cash Return Debit Account',
        domain=[('deprecated', '=', False)],
        help="Account debited when user returns unused cash (typically Cash/Bank).",
    )
    # Workflow
    petty_cash_require_approval = fields.Boolean(
        string='Require Manager Approval', default=True,
    )
    petty_cash_auto_post = fields.Boolean(
        string='Auto-Post After Approval', default=False,
    )
    petty_cash_warn_over_balance = fields.Boolean(
        string='Warn on Over-Balance Approval', default=True,
        help="Show warning when approving expense that exceeds user's available balance.",
    )
    petty_cash_default_opening = fields.Float(default=0.0)
    petty_cash_default_max = fields.Float(default=10000.0)