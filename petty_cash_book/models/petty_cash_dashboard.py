# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, timedelta
import calendar


class PettyCashDashboard(models.TransientModel):
    _name = 'petty.cash.dashboard'
    _description = 'Petty Cash Dashboard'

    date_from = fields.Date(string='From Date', default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='To Date', default=lambda self: date.today())
    account_id = fields.Many2one(
        'account.account',
        string='Petty Cash Account',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # Computed summary fields
    opening_balance = fields.Monetary(
        string='Opening Balance',
        compute='_compute_summary',
    )
    total_received = fields.Monetary(
        string='Total Cash Received',
        compute='_compute_summary',
    )
    total_expenses = fields.Monetary(
        string='Total Expenses',
        compute='_compute_summary',
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        compute='_compute_summary',
    )
    cash_in_hand = fields.Monetary(
        string='Cash in Hand',
        compute='_compute_summary',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends('date_from', 'date_to', 'account_id', 'journal_id', 'company_id')
    def _compute_summary(self):
        for rec in self:
            rec.opening_balance = rec._get_opening_balance()
            received_records = rec._get_received_records()
            expense_records = rec._get_expense_records()
            rec.total_received = sum(received_records.mapped('amount'))
            rec.total_expenses = sum(expense_records.mapped('amount'))
            rec.closing_balance = rec.opening_balance + rec.total_received - rec.total_expenses
            rec.cash_in_hand = rec.closing_balance

    def _get_opening_balance(self):
        """Calculate opening balance before date_from"""
        self.ensure_one()
        if not self.date_from:
            return 0.0

        # Sum all received before date_from
        domain_received = [
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('date', '<', self.date_from),
        ]
        if self.account_id:
            domain_received.append(('cash_account_id', '=', self.account_id.id))
        if self.journal_id:
            domain_received.append(('journal_id', '=', self.journal_id.id))

        domain_expense = [
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('date', '<', self.date_from),
        ]
        if self.account_id:
            domain_expense.append(('cash_account_id', '=', self.account_id.id))
        if self.journal_id:
            domain_expense.append(('journal_id', '=', self.journal_id.id))

        received = self.env['petty.cash.received'].search(domain_received)
        expenses = self.env['petty.cash.expense'].search(domain_expense)
        return sum(received.mapped('amount')) - sum(expenses.mapped('amount'))

    def _get_received_records(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        if self.account_id:
            domain.append(('cash_account_id', '=', self.account_id.id))
        if self.journal_id:
            domain.append(('journal_id', '=', self.journal_id.id))
        return self.env['petty.cash.received'].search(domain, order='date asc')

    def _get_expense_records(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        if self.account_id:
            domain.append(('cash_account_id', '=', self.account_id.id))
        if self.journal_id:
            domain.append(('journal_id', '=', self.journal_id.id))
        return self.env['petty.cash.expense'].search(domain, order='date asc')

    def action_today(self):
        today = date.today()
        self.write({'date_from': today, 'date_to': today})
        return self._reload_action()

    def action_this_week(self):
        today = date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        self.write({'date_from': start, 'date_to': end})
        return self._reload_action()

    def action_this_month(self):
        today = date.today()
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        self.write({'date_from': start, 'date_to': end})
        return self._reload_action()

    def action_last_month(self):
        today = date.today()
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        self.write({'date_from': last_month_start, 'date_to': last_month_end})
        return self._reload_action()

    def action_this_quarter(self):
        today = date.today()
        quarter = (today.month - 1) // 3
        start_month = quarter * 3 + 1
        end_month = start_month + 2
        last_day = calendar.monthrange(today.year, end_month)[1]
        self.write({
            'date_from': date(today.year, start_month, 1),
            'date_to': date(today.year, end_month, last_day),
        })
        return self._reload_action()

    def action_this_year(self):
        today = date.today()
        self.write({
            'date_from': date(today.year, 1, 1),
            'date_to': date(today.year, 12, 31),
        })
        return self._reload_action()

    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Petty Cash Book'),
            'res_model': 'petty.cash.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'main',
        }

    def action_add_received(self):
        # Get defaults
        default_journal = self._get_default_journal()
        default_account = self._get_default_account(default_journal)
        ctx = {
            'default_date': self.date_to or fields.Date.today(),
        }
        if default_journal:
            ctx['default_journal_id'] = default_journal.id
        if default_account:
            ctx['default_cash_account_id'] = default_account.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Cash Received'),
            'res_model': 'petty.cash.received',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_add_expense(self):
        default_journal = self._get_default_journal()
        default_account = self._get_default_account(default_journal)
        ctx = {
            'default_date': self.date_to or fields.Date.today(),
        }
        if default_journal:
            ctx['default_journal_id'] = default_journal.id
        if default_account:
            ctx['default_cash_account_id'] = default_account.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Expense'),
            'res_model': 'petty.cash.expense',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_view_journal_entries(self):
        received_moves = self.env['petty.cash.received'].search([
            ('state', '=', 'posted'),
            ('move_id', '!=', False),
        ]).mapped('move_id')
        expense_moves = self.env['petty.cash.expense'].search([
            ('state', '=', 'posted'),
            ('move_id', '!=', False),
        ]).mapped('move_id')
        all_moves = received_moves | expense_moves
        return {
            'type': 'ir.actions.act_window',
            'name': _('Petty Cash Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_moves.ids)],
        }

    def action_print_report(self):
        return self.env.ref(
            'petty_cash_book.action_petty_cash_book_report'
        ).report_action(self)

    def _get_default_journal(self):
        journal_id = self.env['ir.config_parameter'].sudo().get_param(
            'petty_cash_book.default_journal_id'
        )
        if journal_id:
            return self.env['account.journal'].browse(int(journal_id))
        return self.env['account.journal'].search([
            ('type', 'in', ['cash', 'bank']),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _get_default_account(self, journal=None):
        account_id = self.env['ir.config_parameter'].sudo().get_param(
            'petty_cash_book.default_account_id'
        )
        if account_id:
            return self.env['account.account'].browse(int(account_id))
        if journal and journal.default_account_id:
            return journal.default_account_id
        return False

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, account_id=None, journal_id=None):
        """Returns dashboard data as dict for JSON controller"""
        company = self.env.company
        today = date.today()

        if not date_from:
            date_from = today.replace(day=1)
        if not date_to:
            date_to = today

        # Build domains
        base_domain_received = [
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        base_domain_expense = [
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]

        if account_id:
            base_domain_received.append(('cash_account_id', '=', account_id))
            base_domain_expense.append(('cash_account_id', '=', account_id))
        if journal_id:
            base_domain_received.append(('journal_id', '=', journal_id))
            base_domain_expense.append(('journal_id', '=', journal_id))

        received_records = self.env['petty.cash.received'].search(
            base_domain_received, order='date asc'
        )
        expense_records = self.env['petty.cash.expense'].search(
            base_domain_expense, order='date asc'
        )

        # Opening balance (before date_from)
        ob_domain_received = [
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('date', '<', date_from),
        ]
        ob_domain_expense = [
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
            ('date', '<', date_from),
        ]
        if account_id:
            ob_domain_received.append(('cash_account_id', '=', account_id))
            ob_domain_expense.append(('cash_account_id', '=', account_id))

        ob_received = self.env['petty.cash.received'].search(ob_domain_received)
        ob_expenses = self.env['petty.cash.expense'].search(ob_domain_expense)
        opening_balance = sum(ob_received.mapped('amount')) - sum(ob_expenses.mapped('amount'))

        total_received = sum(received_records.mapped('amount'))
        total_expenses = sum(expense_records.mapped('amount'))
        closing_balance = opening_balance + total_received - total_expenses

        currency = company.currency_id

        return {
            'opening_balance': opening_balance,
            'total_received': total_received,
            'total_expenses': total_expenses,
            'closing_balance': closing_balance,
            'cash_in_hand': closing_balance,
            'currency_symbol': currency.symbol,
            'currency_name': currency.name,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'received_records': [{
                'id': r.id,
                'date': str(r.date),
                'reference': r.reference,
                'partner': r.partner_id.name if r.partner_id else '',
                'description': r.description,
                'received_by': r.received_by.name if r.received_by else '',
                'amount': r.amount,
                'state': r.state,
            } for r in received_records],
            'expense_records': [{
                'id': e.id,
                'date': str(e.date),
                'reference': e.reference,
                'partner': e.partner_id.name if e.partner_id else '',
                'category': e.category_id.name if e.category_id else '',
                'description': e.description,
                'amount': e.amount,
                'state': e.state,
            } for e in expense_records],
        }
