# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PettyCashExpenseCategory(models.Model):
    _name = 'petty.cash.expense.category'
    _description = 'Petty Cash Expense Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Code')
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        domain=[('account_type', 'not in', ['asset_receivable', 'liability_payable'])],
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    expense_count = fields.Integer(
        string='Expenses',
        compute='_compute_expense_count',
    )

    @api.depends('name')
    def _compute_expense_count(self):
        for rec in self:
            rec.expense_count = self.env['petty.cash.expense'].search_count(
                [('category_id', '=', rec.id)]
            )


class PettyCashConfig(models.TransientModel):
    _inherit = 'res.config.settings'

    petty_cash_journal_id = fields.Many2one(
        'account.journal',
        string='Default Petty Cash Journal',
        config_parameter='petty_cash_book.default_journal_id',
        domain=[('type', 'in', ['cash', 'bank'])],
    )
    petty_cash_account_id = fields.Many2one(
        'account.account',
        string='Default Cash Account',
        config_parameter='petty_cash_book.default_account_id',
    )
    petty_cash_allow_negative = fields.Boolean(
        string='Allow Negative Balance',
        config_parameter='petty_cash_book.allow_negative_balance',
        default=False,
    )
