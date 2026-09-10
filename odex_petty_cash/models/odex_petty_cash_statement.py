# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, timedelta
import calendar


class OdexPettyCashStatement(models.TransientModel):
    """
    User Petty Cash Statement — shows full ledger with running balance.
    Used for both User Dashboard and Manager Review.
    One model, domain-filtered per user.
    """
    _name = 'odex.petty.cash.statement'
    _description = 'ODEX Petty Cash Statement'

    petty_cash_account_id = fields.Many2one(
        'odex.petty.cash.account', string='Petty Cash Account', required=True,
    )
    date_from = fields.Date(
        string='From Date', required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='To Date', required=True,
        default=lambda self: date.today(),
    )
    period_type = fields.Selection([
        ('today', 'Today'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
        ('custom', 'Custom'),
    ], default='this_month', string='Period')

    currency_id = fields.Many2one(
        'res.currency', related='petty_cash_account_id.currency_id',
    )

    # ── Summary fields ────────────────────────────────────────────────────
    opening_balance = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Opening Balance',
    )
    total_received = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Total Received',
    )
    total_allocated = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Total Allocated',
    )
    total_spent = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Total Spent (Posted)',
    )
    total_pending = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Pending Approval',
    )
    total_returned = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Total Returned',
    )
    available_balance = fields.Monetary(
        compute='_compute_summary', currency_field='currency_id',
        string='Available Balance',
    )

    @api.onchange('period_type')
    def _onchange_period(self):
        today = date.today()
        if self.period_type == 'today':
            self.date_from = self.date_to = today
        elif self.period_type == 'this_week':
            self.date_from = today - timedelta(days=today.weekday())
            self.date_to = today
        elif self.period_type == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today.replace(
                day=calendar.monthrange(today.year, today.month)[1])
        elif self.period_type == 'last_month':
            first = today.replace(day=1)
            end = first - timedelta(days=1)
            self.date_from, self.date_to = end.replace(day=1), end
        elif self.period_type == 'this_quarter':
            q = (today.month - 1) // 3
            self.date_from = date(today.year, q * 3 + 1, 1)
            lm = q * 3 + 3
            self.date_to = date(today.year, lm,
                                calendar.monthrange(today.year, lm)[1])
        elif self.period_type == 'this_year':
            self.date_from = date(today.year, 1, 1)
            self.date_to = date(today.year, 12, 31)

    @api.depends('petty_cash_account_id', 'date_from', 'date_to')
    def _compute_summary(self):
        for rec in self:
            acc = rec.petty_cash_account_id
            if not acc:
                rec.opening_balance = rec.total_received = rec.total_allocated = \
                    rec.total_spent = rec.total_pending = rec.total_returned = \
                    rec.available_balance = 0
                continue

            base = [('petty_cash_account_id', '=', acc.id), ('state', '=', 'posted')]
            df, dt = rec.date_from, rec.date_to

            # Opening = everything before date_from
            prior_alloc = self.env['odex.petty.cash.allocation'].search(
                base + [('date', '<', df)])
            prior_txn = self.env['odex.petty.cash.transaction'].search(
                base + [('date', '<', df)])
            prior_ret = self.env['odex.petty.cash.return'].search(
                base + [('date', '<', df)])

            prior_in = sum(prior_alloc.mapped('amount'))
            prior_inc = sum(prior_txn.filtered(
                lambda t: t.transaction_type == 'income').mapped('amount'))
            prior_exp = sum(prior_txn.filtered(
                lambda t: t.transaction_type == 'expense').mapped('amount'))
            prior_ret_amt = sum(prior_ret.mapped('amount'))
            rec.opening_balance = (
                acc.opening_balance + prior_in + prior_inc
                - prior_exp - prior_ret_amt
            )

            # Period
            pf = base + [('date', '>=', df), ('date', '<=', dt)]
            period_alloc = self.env['odex.petty.cash.allocation'].search(pf)
            period_txn = self.env['odex.petty.cash.transaction'].search(pf)
            period_ret = self.env['odex.petty.cash.return'].search(pf)
            pending_txn = self.env['odex.petty.cash.transaction'].search([
                ('petty_cash_account_id', '=', acc.id),
                ('state', 'in', ('submitted', 'approved')),
                ('transaction_type', '=', 'expense'),
                ('date', '>=', df), ('date', '<=', dt),
            ])

            rec.total_allocated = sum(period_alloc.mapped('amount'))
            rec.total_received = sum(
                period_txn.filtered(
                    lambda t: t.transaction_type == 'income').mapped('amount'))
            rec.total_spent = sum(
                period_txn.filtered(
                    lambda t: t.transaction_type == 'expense').mapped('amount'))
            rec.total_pending = sum(pending_txn.mapped('amount'))
            rec.total_returned = sum(period_ret.mapped('amount'))
            rec.available_balance = (
                rec.opening_balance + rec.total_allocated + rec.total_received
                - rec.total_spent - rec.total_returned
            )

    def action_print_report(self):
        return self.env.ref(
            'odex_petty_cash.action_report_odex_petty_cash'
        ).report_action(self)

    def action_new_expense(self):
        acc = self.petty_cash_account_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Expense'),
            'res_model': 'odex.petty.cash.transaction',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_petty_cash_account_id': acc.id,
                'default_transaction_type': 'expense',
            },
        }
