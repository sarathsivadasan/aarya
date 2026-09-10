# -*- coding: utf-8 -*-
from odoo import models, fields

class OdexPcSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    petty_cash_journal_id = fields.Many2one(
        'account.journal', 
        related='company_id.petty_cash_journal_id', 
        readonly=False,
        string='Default Petty Cash Journal',
        domain=[('type', 'in', ['cash', 'bank'])]
    )
    petty_cash_gl_account_id = fields.Many2one(
        'account.account', 
        related='company_id.petty_cash_gl_account_id', 
        readonly=False,
        string='Petty Cash GL Account (Asset)'
    )
    cash_receipt_account_id = fields.Many2one(
        'account.account', 
        related='company_id.cash_receipt_account_id', 
        readonly=False,
        string='Cash Receipt Credit Account'
    )
    cash_expense_account_id = fields.Many2one(
        'account.account', 
        related='company_id.cash_expense_account_id', 
        readonly=False,
        string='Default Cash Expense Account'
    )
    cash_return_account_id = fields.Many2one(
        'account.account', 
        related='company_id.cash_return_account_id', 
        readonly=False,
        string='Cash Return Debit Account'
    )
    petty_cash_require_approval = fields.Boolean(
        related='company_id.petty_cash_require_approval', 
        readonly=False, 
        string='Require Manager Approval'
    )
    petty_cash_auto_post = fields.Boolean(
        related='company_id.petty_cash_auto_post', 
        readonly=False, 
        string='Auto-Post After Approval'
    )
    petty_cash_warn_over_balance = fields.Boolean(
        related='company_id.petty_cash_warn_over_balance', 
        readonly=False, 
        string='Warn on Over-Balance Approval'
    )
    petty_cash_default_opening = fields.Float(
        related='company_id.petty_cash_default_opening', 
        readonly=False
    )
    petty_cash_default_max = fields.Float(
        related='company_id.petty_cash_default_max', 
        readonly=False
    )
