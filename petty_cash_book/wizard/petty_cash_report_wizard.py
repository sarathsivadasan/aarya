# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
import calendar


class PettyCashReportWizard(models.TransientModel):
    _name = 'petty.cash.report.wizard'
    _description = 'Petty Cash Report Wizard'

    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.context_today,
    )
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
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # Computed summary fields
    opening_balance = fields.Monetary(compute='_compute_summary')
    total_received = fields.Monetary(compute='_compute_summary')
    total_expenses = fields.Monetary(compute='_compute_summary')
    closing_balance = fields.Monetary(compute='_compute_summary')

    received_line_ids = fields.Many2many(
        'petty.cash.received',
        compute='_compute_summary',
        string='Received Lines',
    )
    expense_line_ids = fields.Many2many(
        'petty.cash.expense',
        compute='_compute_summary',
        string='Expense Lines',
    )

    @api.depends('date_from', 'date_to', 'account_id', 'journal_id', 'company_id')
    def _compute_summary(self):
        for rec in self:
            # Opening balance
            ob_domain_r = [
                ('state', '=', 'posted'),
                ('company_id', '=', rec.company_id.id),
                ('date', '<', rec.date_from),
            ]
            ob_domain_e = [
                ('state', '=', 'posted'),
                ('company_id', '=', rec.company_id.id),
                ('date', '<', rec.date_from),
            ]
            if rec.account_id:
                ob_domain_r.append(('cash_account_id', '=', rec.account_id.id))
                ob_domain_e.append(('cash_account_id', '=', rec.account_id.id))
            if rec.journal_id:
                ob_domain_r.append(('journal_id', '=', rec.journal_id.id))
                ob_domain_e.append(('journal_id', '=', rec.journal_id.id))

            ob_r = self.env['petty.cash.received'].search(ob_domain_r)
            ob_e = self.env['petty.cash.expense'].search(ob_domain_e)
            rec.opening_balance = sum(ob_r.mapped('amount')) - sum(ob_e.mapped('amount'))

            # Period records
            domain_r = [
                ('state', '=', 'posted'),
                ('company_id', '=', rec.company_id.id),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ]
            domain_e = [
                ('state', '=', 'posted'),
                ('company_id', '=', rec.company_id.id),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ]
            if rec.account_id:
                domain_r.append(('cash_account_id', '=', rec.account_id.id))
                domain_e.append(('cash_account_id', '=', rec.account_id.id))
            if rec.journal_id:
                domain_r.append(('journal_id', '=', rec.journal_id.id))
                domain_e.append(('journal_id', '=', rec.journal_id.id))

            received = self.env['petty.cash.received'].search(domain_r, order='date asc')
            expenses = self.env['petty.cash.expense'].search(domain_e, order='date asc')

            rec.received_line_ids = received
            rec.expense_line_ids = expenses
            rec.total_received = sum(received.mapped('amount'))
            rec.total_expenses = sum(expenses.mapped('amount'))
            rec.closing_balance = rec.opening_balance + rec.total_received - rec.total_expenses

    def action_print_pdf(self):
        return self.env.ref(
            'petty_cash_book.action_petty_cash_book_report'
        ).report_action(self)

    def action_print_xlsx(self):
        """Future: Excel export"""
        return self.action_print_pdf()
