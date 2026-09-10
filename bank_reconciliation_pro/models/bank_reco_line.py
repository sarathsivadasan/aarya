# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class BankRecoLine(models.Model):
    _name = 'bank.reco.line'
    _description = 'Bank Reconciliation Line'
    _order = 'date desc, id  desc'

    # ── Core Fields ────────────────────────────────────────────────
    name = fields.Char(string='Reference', required=True, index=True)
    date = fields.Date(string='Date', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Partner', index=True)
    partner_name = fields.Char(
        string='Partner Name',
        related='partner_id.name',
        store=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain=[('type', 'in', ['bank', 'cash'])],
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='journal_id.currency_id',
        store=True,
    )

    debit = fields.Monetary(
        string='Debit (AED)',
        currency_field='company_currency_id',
        default=0.0,
    )
    credit = fields.Monetary(
        string='Credit (AED)',
        currency_field='company_currency_id',
        default=0.0,
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Reconciliation Fields ──────────────────────────────────────
    is_reconciled = fields.Boolean(
        string='Reconciled',
        default=False,
        index=True,
    )
    cleared_date = fields.Date(string='Cleared Date')
    bank_date = fields.Date(string='Bank Date')
    bank_reference = fields.Char(string='Bank Reference')
    notes = fields.Text(string='Notes')

    status = fields.Selection(
        [('pending', 'Pending'), ('reconciled', 'Reconciled')],
        string='Status',
        compute='_compute_status',
        store=True,
        index=True,
    )

    # ── Accounting Link ────────────────────────────────────────────
    move_line_id = fields.Many2one(
        'account.move.line',
        string='Journal Item',
        ondelete='set null',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        ondelete='set null',
    )

    # ── Computed ──────────────────────────────────────────────────
    @api.depends('is_reconciled')
    def _compute_status(self):
        for rec in self:
            rec.status = 'reconciled' if rec.is_reconciled else 'pending'

    # ── Business Methods ──────────────────────────────────────────
    def action_reconcile(self, bank_date=None, bank_reference=None, notes=None):
        """Reconcile this line individually or as part of a batch."""
        for rec in self:
            if rec.is_reconciled:
                continue
            if not bank_date and not rec.bank_date:
                raise UserError(
                    'Please provide a Bank Date before reconciling.'
                )
            effective_date = bank_date or rec.bank_date
            rec.write({
                'is_reconciled': True,
                'cleared_date': effective_date,
                'bank_date': effective_date,
                'bank_reference': bank_reference or rec.bank_reference,
                'notes': notes or rec.notes,
            })
            # Optionally mark linked move line as reconciled
            if rec.move_line_id:
                rec.move_line_id.write({'reconciled': True})

    def action_unreconcile(self):
        """Reverse reconciliation."""
        for rec in self:
            rec.write({
                'is_reconciled': False,
                'cleared_date': False,
                'bank_date': False,
            })

    @api.model
    def fetch_from_accounting(self, journal_id, date_from=None, date_to=None):
        """
        Pull unreconciled account.move.lines from accounting
        and create bank.reco.line records if not already present.
        """
        print("journal_id,,,,,,,,,,", journal_id, date_from, date_to)
        journal = self.env['account.journal'].browse(journal_id)
        if not journal.exists():
            raise UserError('Journal not found.')

        domain = [
            ('journal_id', '=', journal_id),
            ('account_id.account_type', 'in', ['asset_cash', 'liability_current']),
            ('parent_state', '=', 'posted'),
        ]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        print("domain,,,,,,,,,,,,,", domain)

        move_lines = self.env['account.move.line'].search(domain, order='date desc, id desc')
        print("move_lines,,,,,,,,,,", move_lines)
        created = 0
        for ml in move_lines:
            existing = self.search([('move_line_id', '=', ml.id)], limit=1)
            if not existing:
                self.create({
                    'name': ml.move_id.name or ml.name or '/',
                    'date': ml.date,
                    'partner_id': ml.partner_id.id if ml.partner_id else False,
                    'journal_id': ml.journal_id.id,
                    'debit': ml.debit,
                    'credit': ml.credit,
                    'move_line_id': ml.id,
                    'company_id': ml.company_id.id,
                })
                created += 1
        return created

    @api.model
    def get_reconciliation_summary(self, journal_id, reco_date=None):
        """
        Returns summary dict for the dashboard header.
        """
        domain_base = [('journal_id', '=', journal_id)]
        if reco_date:
            domain_base.append(('date', '<=', reco_date))

        all_lines = self.search(domain_base)
        reconciled = all_lines.filtered(lambda l: l.is_reconciled)
        pending = all_lines.filtered(lambda l: not l.is_reconciled)

        total_debit = sum(all_lines.mapped('debit'))
        total_credit = sum(all_lines.mapped('credit'))
        cleared_amount = sum(reconciled.mapped('debit')) - sum(reconciled.mapped('credit'))
        pending_amount = sum(pending.mapped('debit')) - sum(pending.mapped('credit'))

        # Opening balance: debit - credit of all reconciled up to date
        opening_balance = cleared_amount

        difference = total_debit - total_credit - cleared_amount

        return {
            'opening_balance': opening_balance,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'cleared_amount': cleared_amount,
            'pending_amount': abs(pending_amount),
            'difference': difference,
            'is_mismatch': abs(difference) > 0.01,
        }
