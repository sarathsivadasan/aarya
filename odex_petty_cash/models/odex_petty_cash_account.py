# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OdexPettyCashAccount(models.Model):
    """
    One petty cash account per employee/user.
    Balance = opening + total_allocated + total_other_income - total_posted_expenses - total_returned
    Pending/Draft/Rejected expenses do NOT affect the balance.
    """
    _name = 'odex.petty.cash.account'
    _description = 'ODEX Petty Cash Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id'
    _rec_name = 'display_name'

    name = fields.Char(string='Account Name', required=True, tracking=True)
    code = fields.Char(string='Account Code', required=True, tracking=True)

    # ── User / Employee link ─────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True,
        help="This petty cash account belongs exclusively to this employee.",
    )
    user_id = fields.Many2one(
        'res.users', related='employee_id.user_id',
        string='User (Portal/Backend)', store=True, index=True,
    )
    petty_cash_manager_id = fields.Many2one(
        'hr.employee', related='employee_id.petty_cash_manager_id',
        string='Petty Cash Manager', store=True,
    )
    petty_cash_manager_user_id = fields.Many2one(
        'res.users', related='employee_id.petty_cash_manager_user_id',
        string='Manager (User)', store=True, index=True,
    )

    # ── GL Accounts (inherit from company settings, override here if needed) ─
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
        default=lambda self: self.env.company.petty_cash_journal_id,
    )
    account_id = fields.Many2one(
        'account.account', string='Petty Cash GL Account',
        domain=[('deprecated', '=', False)],
        default=lambda self: self.env.company.petty_cash_gl_account_id,
    )
    cash_receipt_account_id = fields.Many2one(
        'account.account', string='Cash Receipt Credit Account',
        domain=[('deprecated', '=', False)],
        default=lambda self: self.env.company.cash_receipt_account_id,
    )
    default_expense_account_id = fields.Many2one(
        'account.account', string='Default Expense Account',
        domain=[('deprecated', '=', False)],
        default=lambda self: self.env.company.cash_expense_account_id,
    )
    cash_return_account_id = fields.Many2one(
        'account.account', string='Cash Return Account',
        domain=[('deprecated', '=', False)],
        default=lambda self: self.env.company.cash_return_account_id,
    )

    opening_balance = fields.Monetary(
        string='Opening Balance', currency_field='currency_id',
        default=lambda self: self.env.company.petty_cash_default_opening,
        tracking=True,
    )
    max_amount = fields.Monetary(
        string='Maximum Limit', currency_field='currency_id',
        default=lambda self: self.env.company.petty_cash_default_max,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    note = fields.Text()

    # ── Related records ──────────────────────────────────────────────────
    allocation_ids = fields.One2many('odex.petty.cash.allocation', 'petty_cash_account_id')
    transaction_ids = fields.One2many('odex.petty.cash.transaction', 'petty_cash_account_id')
    return_ids = fields.One2many('odex.petty.cash.return', 'petty_cash_account_id')

    # ── Balance Fields ───────────────────────────────────────────────────
    total_received = fields.Monetary(
        string='Total Received', compute='_compute_balance',
        currency_field='currency_id', store=True,
    )
    total_posted_expenses = fields.Monetary(
        string='Total Spent (Posted)', compute='_compute_balance',
        currency_field='currency_id', store=True,
    )
    total_pending_expenses = fields.Monetary(
        string='Total Pending', compute='_compute_balance',
        currency_field='currency_id', store=True,
    )
    total_returned = fields.Monetary(
        string='Total Returned', compute='_compute_balance',
        currency_field='currency_id', store=True,
    )
    available_balance = fields.Monetary(
        string='Available Balance', compute='_compute_balance',
        currency_field='currency_id', store=True,
        help="= Opening + Total Received - Posted Expenses - Returned cash.\n"
             "Pending/Draft/Rejected expenses do NOT reduce this balance.",
    )

    @api.depends(
        'opening_balance',
        'allocation_ids.state', 'allocation_ids.amount',
        'transaction_ids.state', 'transaction_ids.amount', 'transaction_ids.transaction_type',
        'return_ids.state', 'return_ids.amount',
    )
    def _compute_balance(self):
        for rec in self:
            # ── RECEIVED: posted allocations + posted income transactions ──
            posted_allocs = rec.allocation_ids.filtered(lambda a: a.state == 'posted')
            posted_income = rec.transaction_ids.filtered(
                lambda t: t.state == 'posted' and t.transaction_type == 'income'
            )
            total_received = (
                sum(posted_allocs.mapped('amount'))
                + sum(posted_income.mapped('amount'))
            )

            # ── SPENT: only posted expense transactions affect balance ──
            posted_expenses = rec.transaction_ids.filtered(
                lambda t: t.state == 'posted' and t.transaction_type == 'expense'
            )
            total_posted_exp = sum(posted_expenses.mapped('amount'))

            # ── PENDING: submitted or approved (not yet posted) expenses ──
            pending_expenses = rec.transaction_ids.filtered(
                lambda t: t.state in ('submitted', 'approved')
                and t.transaction_type == 'expense'
            )
            total_pending = sum(pending_expenses.mapped('amount'))

            # ── RETURNED: posted returns ──
            posted_returns = rec.return_ids.filtered(lambda r: r.state == 'posted')
            total_returned = sum(posted_returns.mapped('amount'))

            rec.total_received = total_received
            rec.total_posted_expenses = total_posted_exp
            rec.total_pending_expenses = total_pending
            rec.total_returned = total_returned
            rec.available_balance = (
                rec.opening_balance + total_received - total_posted_exp - total_returned
            )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'employee_id')
    def _compute_display_name(self):
        for r in self:
            r.display_name = (
                f"{r.employee_id.name} — {r.name}" if r.employee_id else r.name
            )

    _sql_constraints = [
        ('employee_unique', 'unique(employee_id, company_id)',
         'One petty cash account per employee per company!'),
        ('code_company_unique', 'unique(code, company_id)',
         'Account code must be unique per company!'),
    ]

    # ── Smart button actions ──────────────────────────────────────────────
    def action_view_allocations(self):
        return self._window_action('odex.petty.cash.allocation', 'Cash Allocations')

    def action_view_expenses(self):
        return self._window_action(
            'odex.petty.cash.transaction', 'Expenses',
            domain_extra=[('transaction_type', '=', 'expense')],
        )

    def action_view_returns(self):
        return self._window_action('odex.petty.cash.return', 'Cash Returns')

    def action_view_statement(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Petty Cash Statement — %s') % self.employee_id.name,
            'res_model': 'odex.petty.cash.statement',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_petty_cash_account_id': self.id},
        }

    def _window_action(self, model, name, domain_extra=None):
        domain = [('petty_cash_account_id', '=', self.id)]
        if domain_extra:
            domain += domain_extra
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain,
        }


class OdexPettyCashCategory(models.Model):
    _name = 'odex.petty.cash.category'
    _description = 'ODEX Petty Cash Expense Category'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    account_id = fields.Many2one(
        'account.account', string='Expense GL Account',
        domain=[('deprecated', '=', False)],
        help="Debited when an expense in this category is posted.",
    )
    analytic_account_id = fields.Many2one('account.analytic.account')
    account_code = fields.Char(related='account_id.code', store=True)
    account_mapped = fields.Boolean(compute='_compute_mapped', store=True)

    @api.depends('account_id')
    def _compute_mapped(self):
        for r in self:
            r.account_mapped = bool(r.account_id)

    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [('name_unique', 'unique(name)', 'Category name must be unique!')]
