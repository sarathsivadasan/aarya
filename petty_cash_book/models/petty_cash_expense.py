# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PettyCashExpense(models.Model):
    _name = 'petty.cash.expense'
    _description = 'Petty Cash Expense (Spending)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'reference'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='To (Partner)',
        tracking=True,
    )
    category_id = fields.Many2one(
        'petty.cash.expense.category',
        string='Category',
        tracking=True,
    )
    description = fields.Char(
        string='Description',
        required=True,
        tracking=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain=[('code', 'in', ['PCSH'])], default=lambda self: self.env['account.journal'].search(
        [('code', '=', 'PCSH')],
        limit=1
    )
    )
    cash_account_id = fields.Many2one(
        'account.account',
        string='Cash Account',
        required=True,
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        domain=[('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost'])],
    )
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('reference', 'description')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.reference or rec.description or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'petty.cash.expense'
                ) or 'New'
        return super().create(vals_list)

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id and self.journal_id.default_account_id:
            self.cash_account_id = self.journal_id.default_account_id

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id and self.category_id.account_id:
            self.expense_account_id = self.category_id.account_id

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft records can be posted.'))
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

            # Check negative balance
            allow_negative = self.env['ir.config_parameter'].sudo().get_param(
                'petty_cash_book.allow_negative_balance', 'False'
            )
            if allow_negative != 'True':
                available = rec._get_available_balance()
                if rec.amount > available:
                    raise ValidationError(
                        _('Insufficient petty cash balance. Available: %s, Required: %s')
                        % (rec.currency_id.symbol + str(available), rec.currency_id.symbol + str(rec.amount))
                    )

            rec._create_journal_entry()
            rec.state = 'posted'

    def _get_available_balance(self):
        """Get available cash balance from the cash account"""
        self.ensure_one()
        domain = [
            ('account_id', '=', self.cash_account_id.id),
            ('parent_state', '=', 'posted'),
        ]
        lines = self.env['account.move.line'].search(domain)
        balance = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))
        return balance

    def action_draft(self):
        for rec in self:
            if rec.move_id:
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
                rec.move_id = False
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.move_id:
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = 'cancelled'

    def _create_journal_entry(self):
        self.ensure_one()
        expense_account = self.expense_account_id or self._get_expense_account()
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.reference,
            'company_id': self.company_id.id,
            'line_ids': [
                (0, 0, {
                    'account_id': self.expense_account_id.id,  # Petty Cash Account
                    'name': self.description,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'debit': self.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                }),
                (0, 0, {
                    'account_id': self.cash_account_id.id,  # Cash Account
                    'name': self.description,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'debit': 0.0,
                    'credit': self.amount,
                    'currency_id': self.currency_id.id,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.move_id = move

    def _get_expense_account(self):
        domain = [
            ('company_ids', 'in', [self.company_id.id]),
            ('account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost']),
            ('deprecated', '=', False),
        ]
        account = self.env['account.account'].search(domain, limit=1)
        if not account:
            raise UserError(_('No expense account found. Please configure one in the category or expense account field.'))
        return account

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No journal entry found.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    def unlink(self):
        for rec in self:
            if rec.state == 'posted':
                raise UserError(_('You cannot delete a posted record. Please cancel it first.'))
        return super().unlink()
