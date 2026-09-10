# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('posted', 'Posted'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]


class OdexPettyCashReturn(models.Model):
    """Employee returns unused cash to company."""
    _name = 'odex.petty.cash.return'
    _description = 'ODEX Petty Cash Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(readonly=True, copy=False, default='/')
    petty_cash_account_id = fields.Many2one(
        'odex.petty.cash.account', required=True, tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee', related='petty_cash_account_id.employee_id',
        string='Employee', store=True,
    )
    user_id = fields.Many2one(
        'res.users', related='petty_cash_account_id.user_id',
        string='User', store=True,
    )
    petty_cash_manager_user_id = fields.Many2one(
        'res.users', related='petty_cash_account_id.petty_cash_manager_user_id',
        store=True,
    )
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    amount = fields.Monetary(required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', related='petty_cash_account_id.currency_id', store=True,
    )
    reason = fields.Text(string='Reason / Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    state = fields.Selection(STATES, default='draft', tracking=True, copy=False)
    submitted_by = fields.Many2one('res.users', readonly=True, copy=False)
    submitted_date = fields.Datetime(readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    rejected_by = fields.Many2one('res.users', readonly=True, copy=False)
    rejected_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(copy=False)
    posted_by = fields.Many2one('res.users', readonly=True, copy=False)
    posted_date = fields.Datetime(readonly=True, copy=False)

    move_id = fields.Many2one('account.move', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', related='petty_cash_account_id.company_id', store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', '/') == '/':
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.petty.cash.return') or '/'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for r in self:
            if r.amount <= 0:
                raise ValidationError(_('Return amount must be > 0.'))
            bal = r.petty_cash_account_id.available_balance
            if r.amount > bal:
                raise ValidationError(_(
                    'Return amount (%.2f) exceeds available balance (%.2f).'
                ) % (r.amount, bal))

    def action_submit(self):
        for r in self:
            r.write({
                'state': 'submitted',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
            r.message_post(
                body=_('📤 Return submitted by <b>%s</b>.') % self.env.user.name,
                subtype_xmlid='mail.mt_comment',
            )
            if r.petty_cash_manager_user_id:
                r.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=r.petty_cash_manager_user_id.id,
                    summary=_('Cash Return Approval — %s') % r.name,
                    note=_('%s returning %s %s.') % (
                        r.employee_id.name, r.currency_id.symbol, r.amount),
                )

    def action_approve(self):
        for r in self:
            if r.user_id == self.env.user and not self.env.user.has_group(
                'odex_petty_cash.group_petty_cash_finance_admin'
            ):
                raise UserError(_('You cannot approve your own return.'))
            r.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            r.message_post(
                body=_('✅ Approved by <b>%s</b>.') % self.env.user.name,
                subtype_xmlid='mail.mt_comment',
            )
            r.activity_feedback(['mail.mail_activity_data_todo'])
            if self.env.company.petty_cash_auto_post:
                r.action_post()

    def action_reject(self, reason=''):
        for r in self:
            r.write({
                'state': 'rejected',
                'rejected_by': self.env.user.id,
                'rejected_date': fields.Datetime.now(),
                'rejection_reason': reason,
            })
            r.message_post(
                body=_('❌ Rejected by <b>%s</b>. Reason: %s') % (
                    self.env.user.name, reason or '—'),
                subtype_xmlid='mail.mt_comment',
            )
            r.activity_feedback(['mail.mail_activity_data_todo'])

    def action_post(self):
        for r in self:
            r._create_journal_entry()
            r.write({
                'state': 'posted',
                'posted_by': self.env.user.id,
                'posted_date': fields.Datetime.now(),
            })
            r.message_post(
                body=_('📒 Posted by <b>%s</b>. Journal Entry: <b>%s</b>') % (
                    self.env.user.name, r.move_id.name),
                subtype_xmlid='mail.mt_comment',
            )

    def action_cancel(self):
        for r in self:
            if r.state == 'posted' and r.move_id:
                r.move_id.button_cancel()
                r.move_id.unlink()
            r.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for r in self:
            if r.state in ('rejected', 'cancelled'):
                r.write({'state': 'draft'})

    def _create_journal_entry(self):
        """DR Cash/Bank / CR Employee Petty Cash GL"""
        self.ensure_one()
        acc = self.petty_cash_account_id
        journal = acc.journal_id
        petty_gl = acc.account_id
        debit_gl = acc.cash_return_account_id or self.env.company.cash_return_account_id
        if not debit_gl:
            raise UserError(_(
                "No Cash Return Debit Account.\n"
                "Set in ODEX Petty Cash → Settings → Cash Return Debit Account."
            ))
        partner_id = (acc.employee_id.address_home_id.id
                      if acc.employee_id.address_home_id else False)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'narration': self.reason or '',
            'line_ids': [
                (0, 0, {'name': _('Cash Return from %s') % acc.employee_id.name,
                         'account_id': debit_gl.id,
                         'debit': self.amount, 'credit': 0.0, 'partner_id': partner_id}),
                (0, 0, {'name': _('Cash Return from %s') % acc.employee_id.name,
                         'account_id': petty_gl.id,
                         'debit': 0.0, 'credit': self.amount, 'partner_id': partner_id}),
            ],
        })
        move.action_post()
        self.move_id = move.id
