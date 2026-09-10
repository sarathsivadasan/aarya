# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('posted', 'Posted'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]


class OdexPettyCashTransaction(models.Model):
    """
    User's petty cash expense or misc cash receipt.
    - Only POSTED expenses reduce the user's available balance.
    - Draft / Submitted / Rejected / Cancelled = no balance impact.
    - Pending (submitted/approved) shown separately for awareness.
    - Over-balance warning shown to approver.
    """
    _name = 'odex.petty.cash.transaction'
    _description = 'ODEX Petty Cash Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(readonly=True, copy=False, default='/')
    petty_cash_account_id = fields.Many2one(
        'odex.petty.cash.account', string='Petty Cash Account',
        required=True, tracking=True, ondelete='restrict',
    )
    employee_id = fields.Many2one(
        'hr.employee', related='petty_cash_account_id.employee_id',
        string='Employee', store=True,
    )
    user_id = fields.Many2one(
        'res.users', related='petty_cash_account_id.user_id',
        string='User', store=True, index=True,
    )
    petty_cash_manager_user_id = fields.Many2one(
        'res.users', related='petty_cash_account_id.petty_cash_manager_user_id',
        string='Approver', store=True, index=True,
    )

    transaction_type = fields.Selection([
        ('income', 'Cash Received'),
        ('expense', 'Expense'),
    ], string='Type', required=True, tracking=True, default='expense')

    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Vendor / Payee', tracking=True)
    description = fields.Char(string='Description', required=True, tracking=True)
    amount = fields.Monetary(required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', related='petty_cash_account_id.currency_id', store=True,
    )
    category_id = fields.Many2one(
        'odex.petty.cash.category', string='Category', tracking=True,
        help="Expense category. Its GL account overrides the default expense account.",
    )
    received_by = fields.Many2one(
        'res.users', string='Received By',
        default=lambda self: self.env.user,
    )
    attachment_ids = fields.Many2many('ir.attachment', string='Receipt / Attachments')
    note = fields.Text(string='Notes')

    # ── Approval trail ────────────────────────────────────────────────────
    state = fields.Selection(STATES, default='draft', tracking=True, copy=False)
    submitted_by = fields.Many2one('res.users', readonly=True, copy=False,
                                   string='Submitted By')
    submitted_date = fields.Datetime(readonly=True, copy=False, string='Submitted On')
    approved_by = fields.Many2one('res.users', readonly=True, copy=False,
                                  string='Approved By')
    approved_date = fields.Datetime(readonly=True, copy=False, string='Approved On')
    rejected_by = fields.Many2one('res.users', readonly=True, copy=False,
                                  string='Rejected By')
    rejected_date = fields.Datetime(readonly=True, copy=False, string='Rejected On')
    rejection_reason = fields.Text(copy=False, string='Rejection Reason')
    posted_by = fields.Many2one('res.users', readonly=True, copy=False,
                                string='Posted By')
    posted_date = fields.Datetime(readonly=True, copy=False, string='Posted On')

    move_id = fields.Many2one('account.move', readonly=True, copy=False,
                              string='Journal Entry')
    company_id = fields.Many2one(
        'res.company', related='petty_cash_account_id.company_id', store=True,
    )

    # ── Balance snapshot at time of approval ─────────────────────────────
    balance_before = fields.Monetary(
        string='Balance Before', readonly=True, copy=False,
        currency_field='currency_id',
        help="User's available balance at the time of approval.",
    )
    balance_after = fields.Monetary(
        string='Balance After', readonly=True, copy=False,
        currency_field='currency_id',
        help="Projected balance after this expense is approved.",
    )

    # ── GL preview ────────────────────────────────────────────────────────
    effective_debit_account_id = fields.Many2one(
        'account.account', compute='_compute_effective_gl', store=False,
    )
    effective_credit_account_id = fields.Many2one(
        'account.account', compute='_compute_effective_gl', store=False,
    )
    gl_warning_msg = fields.Char(compute='_compute_effective_gl', store=False)

    @api.depends('transaction_type', 'petty_cash_account_id', 'category_id')
    def _compute_effective_gl(self):
        for r in self:
            acc = r.petty_cash_account_id
            petty_gl = acc.account_id if acc else False
            msg = False
            if r.transaction_type == 'income':
                debit, credit = petty_gl, (acc.cash_receipt_account_id if acc else False)
                if acc and not credit:
                    msg = "⚠ No Cash Receipt Credit Account. Set in Settings."
            elif r.transaction_type == 'expense':
                if r.category_id and r.category_id.account_id:
                    debit = r.category_id.account_id
                elif acc and acc.default_expense_account_id:
                    debit = acc.default_expense_account_id
                    if r.category_id:
                        msg = "ℹ Category has no GL — using default expense account."
                else:
                    debit = petty_gl
                    msg = "⚠ No expense GL. Set Default Cash Expense Account in Settings."
                credit = petty_gl
            else:
                debit = credit = False
            r.effective_debit_account_id = debit
            r.effective_credit_account_id = credit
            r.gl_warning_msg = msg

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', '/') == '/':
                seq = ('odex.petty.cash.income'
                       if v.get('transaction_type') == 'income'
                       else 'odex.petty.cash.expense')
                v['name'] = self.env['ir.sequence'].next_by_code(seq) or '/'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for r in self:
            if r.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    @api.onchange('petty_cash_account_id')
    def _onchange_account(self):
        """Lock account to logged-in user's account (non-manager)."""
        if not self.env.user.has_group('odex_petty_cash.group_petty_cash_manager'):
            my_account = self.env['odex.petty.cash.account'].search(
                [('user_id', '=', self.env.user.id)], limit=1
            )
            if my_account:
                self.petty_cash_account_id = my_account

    # ── Workflow ──────────────────────────────────────────────────────────
    def action_submit(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('Only draft transactions can be submitted.'))
            r.write({
                'state': 'submitted',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
            r.message_post(
                body=_('📤 Submitted for approval by <b>%s</b>.') % self.env.user.name,
                subtype_xmlid='mail.mt_comment',
            )
            mgr = r.petty_cash_manager_user_id
            if mgr:
                r.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=mgr.id,
                    summary=_('Expense Approval Required — %s') % r.name,
                    note=_(
                        '<b>%s</b> submitted expense <b>%s %s</b> on %s.<br/>'
                        'Description: %s'
                    ) % (
                        r.employee_id.name,
                        r.currency_id.symbol, r.amount,
                        r.date, r.description,
                    ),
                )

    def action_approve(self):
        """Manager approves expense — records balance snapshot, warns if over-balance."""
        for r in self:
            # Prevent self-approval
            if r.user_id == self.env.user and not self.env.user.has_group(
                'odex_petty_cash.group_petty_cash_finance_admin'
            ):
                raise UserError(_('You cannot approve your own expense.'))
            if r.state != 'submitted':
                raise UserError(_('Only submitted expenses can be approved.'))

            # Balance check
            acc = r.petty_cash_account_id
            balance_before = acc.available_balance
            balance_after = balance_before - r.amount

            if balance_after < 0 and self.env.company.petty_cash_warn_over_balance:
                # Return warning — Odoo 18 approach: raise with type warning
                raise UserError(_(
                    "⚠ Insufficient Petty Cash Balance!\n\n"
                    "Employee: %s\n"
                    "Available Balance: %s %s\n"
                    "Expense Amount:    %s %s\n"
                    "Shortfall:         %s %s\n\n"
                    "The user does not have sufficient petty cash to cover this expense.\n"
                    "You may still approve by ignoring this warning, or request the user "
                    "to request additional cash allocation first."
                ) % (
                    r.employee_id.name,
                    r.currency_id.symbol, balance_before,
                    r.currency_id.symbol, r.amount,
                    r.currency_id.symbol, abs(balance_after),
                ))

            r.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'balance_before': balance_before,
                'balance_after': balance_after,
            })
            r.message_post(
                body=_(
                    '✅ Approved by <b>%s</b>.<br/>'
                    'Balance before: %s %s | After posting: %s %s'
                ) % (
                    self.env.user.name,
                    r.currency_id.symbol, balance_before,
                    r.currency_id.symbol, balance_after,
                ),
                subtype_xmlid='mail.mt_comment',
            )
            r.activity_feedback(['mail.mail_activity_data_todo'])
            # Notify employee
            if r.user_id:
                r.message_notify(
                    partner_ids=[r.user_id.partner_id.id],
                    subject=_('Expense Approved — %s') % r.name,
                    body=_('Your expense <b>%s</b> (%s %s) has been approved.') % (
                        r.description, r.currency_id.symbol, r.amount),
                )
            if self.env.company.petty_cash_auto_post:
                r.action_post()

    def action_approve_override(self):
        """Force-approve even if over-balance (Finance Admin only)."""
        if not self.env.user.has_group('odex_petty_cash.group_petty_cash_finance_admin'):
            raise UserError(_('Only Finance Admin can override balance check.'))
        for r in self:
            acc = r.petty_cash_account_id
            balance_before = acc.available_balance
            balance_after = balance_before - r.amount
            r.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'balance_before': balance_before,
                'balance_after': balance_after,
            })
            r.message_post(
                body=_(
                    '✅ Approved (Override) by <b>%s</b>. '
                    'Balance before: %s %s (will go negative after posting).'
                ) % (self.env.user.name, r.currency_id.symbol, balance_before),
                subtype_xmlid='mail.mt_comment',
            )
            r.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self, reason=''):
        for r in self:
            if r.state not in ('submitted', 'approved'):
                raise UserError(_('Cannot reject from current state.'))
            r.write({
                'state': 'rejected',
                'rejected_by': self.env.user.id,
                'rejected_date': fields.Datetime.now(),
                'rejection_reason': reason,
            })
            r.message_post(
                body=_('❌ Rejected by <b>%s</b>.<br/>Reason: %s') % (
                    self.env.user.name, reason or '—'),
                subtype_xmlid='mail.mt_comment',
            )
            r.activity_feedback(['mail.mail_activity_data_todo'])
            if r.user_id:
                r.message_notify(
                    partner_ids=[r.user_id.partner_id.id],
                    subject=_('Expense Rejected — %s') % r.name,
                    body=_('Your expense <b>%s</b> was rejected. Reason: %s') % (
                        r.name, reason or '—'),
                )

    def action_send_back(self):
        for r in self:
            r.write({'state': 'draft'})
            r.message_post(
                body=_('↩ Sent back for correction by <b>%s</b>.') % self.env.user.name,
                subtype_xmlid='mail.mt_comment',
            )

    def action_post(self):
        """Post — creates journal entry, balance impact happens here."""
        for r in self:
            if r.state not in ('approved',) and not self.env.user.has_group(
                'odex_petty_cash.group_petty_cash_finance_admin'
            ):
                raise UserError(_('Only approved transactions can be posted.'))
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
            # Notify employee
            if r.user_id and r.transaction_type == 'expense':
                r.message_notify(
                    partner_ids=[r.user_id.partner_id.id],
                    subject=_('Expense Paid/Posted — %s') % r.name,
                    body=_('Your expense <b>%s</b> (%s %s) has been paid and posted.') % (
                        r.description, r.currency_id.symbol, r.amount),
                )

    def action_cancel(self):
        for r in self:
            if r.state == 'posted' and r.move_id:
                r.move_id.button_cancel()
                r.move_id.unlink()
            r.write({'state': 'cancelled'})
            r.message_post(body=_('Cancelled.'), subtype_xmlid='mail.mt_comment')

    def action_reset_draft(self):
        for r in self:
            if r.state in ('rejected', 'cancelled'):
                r.write({'state': 'draft'})
                r.message_post(body=_('Reset to Draft.'), subtype_xmlid='mail.mt_comment')

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No journal entry found.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_journal_entry(self):
        """
        INCOME:  DR Petty Cash GL  / CR Cash Receipt Account
        EXPENSE: DR Category GL (or default) / CR Petty Cash GL
        """
        self.ensure_one()
        acc = self.petty_cash_account_id
        journal = acc.journal_id
        petty_gl = acc.account_id
        partner_id = self.partner_id.id if self.partner_id else False

        if not journal:
            raise UserError(_("No journal. Configure in ODEX Petty Cash → Settings."))
        if not petty_gl:
            raise UserError(_("No Petty Cash GL Account. Configure in Settings."))

        if self.transaction_type == 'income':
            credit_gl = acc.cash_receipt_account_id
            if not credit_gl:
                raise UserError(_(
                    "No Cash Receipt Credit Account on '%s'.\n"
                    "Fix in ODEX Petty Cash → Settings.") % acc.name)
            lines = [
                (0, 0, {'name': self.description, 'account_id': petty_gl.id,
                         'debit': self.amount, 'credit': 0.0, 'partner_id': partner_id}),
                (0, 0, {'name': self.description, 'account_id': credit_gl.id,
                         'debit': 0.0, 'credit': self.amount, 'partner_id': partner_id}),
            ]
        else:
            if self.category_id and self.category_id.account_id:
                expense_gl = self.category_id.account_id
            elif acc.default_expense_account_id:
                expense_gl = acc.default_expense_account_id
                _logger.info(
                    "Expense %s: category '%s' has no GL, using default '%s'",
                    self.name,
                    self.category_id.name if self.category_id else '-',
                    expense_gl.name,
                )
            else:
                raise UserError(_(
                    "No expense GL for '%s'.\n"
                    "Map a GL to category '%s' or set Default Expense Account in Settings."
                ) % (self.name, self.category_id.name if self.category_id else 'None'))

            analytic = {}
            if self.category_id and self.category_id.analytic_account_id:
                analytic = {str(self.category_id.analytic_account_id.id): 100}

            lines = [
                (0, 0, {'name': self.description, 'account_id': expense_gl.id,
                         'debit': self.amount, 'credit': 0.0, 'partner_id': partner_id,
                         'analytic_distribution': analytic or False}),
                (0, 0, {'name': self.description, 'account_id': petty_gl.id,
                         'debit': 0.0, 'credit': self.amount, 'partner_id': partner_id}),
            ]

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'narration': self.note or '',
            'line_ids': lines,
        })
        move.action_post()
        self.move_id = move.id
