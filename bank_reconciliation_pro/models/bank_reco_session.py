# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json


class BankRecoSession(models.TransientModel):
    """
    Transient model used by the OWL component to hold session state
    and perform server-side actions via RPC.
    """
    _name = 'bank.reco.session'
    _description = 'Bank Reconciliation Session'

    journal_id = fields.Many2one(
        'account.journal',
        string='Bank Account',
        domain=[('type', 'in', ['bank', 'cash'])],
        required=True,
    )
    reco_date = fields.Date(
        string='Reconciliation Date',
        default=fields.Date.today,
    )
    bank_date = fields.Date(string='Bank Date', default=fields.Date.today)
    bank_reference = fields.Char(string='Bank Reference')
    notes = fields.Text(string='Notes')
    show_reconciled = fields.Boolean(string='Show Reconciled', default=False)

    @api.model
    def get_lines(self, journal_id, reco_date=None, show_reconciled=False,
                  search_term='', journal_filter='all', partner_filter='all'):
        """
        RPC method: return line data for the OWL component.
        """
        domain = [('journal_id', '=', journal_id)]
        if reco_date:
            domain.append(('date', '<=', reco_date))
        if not show_reconciled:
            domain.append(('is_reconciled', '=', False))

        if search_term:
            domain += [
                '|', '|',
                ('name', 'ilike', search_term),
                ('partner_name', 'ilike', search_term),
                ('debit', 'like', search_term),
            ]
        if journal_filter and journal_filter != 'all':
            domain.append(('journal_id', '=', int(journal_filter)))
        if partner_filter and partner_filter != 'all':
            domain.append(('partner_id', '=', int(partner_filter)))

        lines = self.env['bank.reco.line'].search(domain, order='date desc, create_date desc')
        result = []
        for l in lines:
            result.append({
                'id': l.id,
                'date': l.date.strftime('%d/%m/%Y') if l.date else '',
                'name': l.name,
                'partner': l.partner_name or '',
                'journal': l.journal_id.name if l.journal_id else '',
                'debit': l.debit,
                'credit': l.credit,
                'cleared_date': l.cleared_date.strftime('%d/%m/%Y') if l.cleared_date else '',
                'status': l.status,
                'is_reconciled': l.is_reconciled,
            })
        return result

    @api.model
    def reconcile_lines(self, line_ids, bank_date, bank_reference='', notes=''):
        """
        RPC method: reconcile selected lines.
        """
        if not bank_date:
            raise UserError(_('Bank Date is required to reconcile entries.'))
        lines = self.env['bank.reco.line'].browse(line_ids)
        lines.action_reconcile(
            bank_date=bank_date,
            bank_reference=bank_reference,
            notes=notes,
        )
        return {'success': True, 'count': len(lines)}

    @api.model
    def fetch_transactions(self, journal_id, reco_date=None):
        """
        RPC method: pull transactions from accounting.
        """
        count = self.env['bank.reco.line'].fetch_from_accounting(
            journal_id, date_to=reco_date
        )
        return {'fetched': count}

    @api.model
    def get_summary(self, journal_id, reco_date=None):
        """
        RPC method: return summary dashboard data.
        """
        return self.env['bank.reco.line'].get_reconciliation_summary(
            journal_id, reco_date
        )

    @api.model
    def get_journals(self):
        """Return bank/cash journals for selector."""
        journals = self.env['account.journal'].search(
            [('type', 'in', ['bank', 'cash'])],
            order='name asc'
        )
        return [{'id': j.id, 'name': j.name} for j in journals]

    @api.model
    def reset_reconciliation(self, journal_id, reco_date=None):
        """Unreconcile all lines for a journal (Manager only)."""
        self.env['res.users'].check_access_rights('write')
        domain = [('journal_id', '=', journal_id)]
        if reco_date:
            domain.append(('date', '<=', reco_date))
        lines = self.env['bank.reco.line'].search(domain)
        lines.action_unreconcile()
        return {'reset': len(lines)}

    @api.model
    def create_adjustment_entry(self, journal_id, amount, date, notes=''):
        """Create an adjustment journal entry."""
        journal = self.env['account.journal'].browse(journal_id)
        if not journal.exists():
            raise UserError(_('Journal not found.'))
        # Create a simple manual journal entry
        move_vals = {
            'journal_id': journal_id,
            'date': date,
            'ref': notes or 'Bank Reconciliation Adjustment',
            'line_ids': [
                (0, 0, {
                    'name': 'Adjustment Debit',
                    'account_id': journal.default_account_id.id,
                    'debit': amount if amount > 0 else 0,
                    'credit': -amount if amount < 0 else 0,
                }),
                (0, 0, {
                    'name': 'Adjustment Credit',
                    'account_id': journal.suspense_account_id.id
                    if journal.suspense_account_id
                    else journal.default_account_id.id,
                    'debit': -amount if amount < 0 else 0,
                    'credit': amount if amount > 0 else 0,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        return {'move_id': move.id, 'name': move.name}
