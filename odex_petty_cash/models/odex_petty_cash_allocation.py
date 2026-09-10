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


class OdexPettyCashAllocation(models.Model):
    """
    Finance/Manager issues cash TO a user.
    After posting: DR Employee Petty Cash GL / CR Cash Receipt Account.
    Only posted allocations increase the user's available balance.
    """
    _name = 'odex.petty.cash.allocation'
    _description = 'ODEX Petty Cash Allocation'
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
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ], string='Payment Method', default='cash')
    reference = fields.Char(string='Reference / Voucher No.')
    source_account_id = fields.Many2one(
        'account.account', string='Source / Cash Account',
        domain=[('deprecated', '=', False)],
        help="The cash/bank account from which money is issued.",
    )
    notes = fields.Text()
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
        default=lambda self: self.env.company.petty_cash_journal_id,
    )

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
                    'odex.petty.cash.allocation') or '/'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for r in self:
            if r.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    # ── Workflow ─────────────────────────────────────────────────────────
    def action_submit(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('Only draft allocations can be submitted.'))
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
                    summary=_('Cash Allocation Approval — %s') % r.name,
                    note=_('AED %s to be allocated to %s.') % (r.amount, r.employee_id.name),
                )

    def action_approve(self):
        for r in self:
            if r.employee_id.user_id == self.env.user and not self.env.user.has_group(
                'odex_petty_cash.group_petty_cash_finance_admin'
            ):
                raise UserError(_('You cannot approve your own allocation request.'))
            if r.state != 'submitted':
                raise UserError(_('Only submitted allocations can be approved.'))
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
            if r.user_id:
                r.message_notify(
                    partner_ids=[r.user_id.partner_id.id],
                    subject=_('Cash Allocation Approved — %s') % r.name,
                    body=_('%s %s has been allocated to you.') % (
                        r.currency_id.symbol, r.amount),
                )
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
            if r.state not in ('approved',) and not self.env.user.has_group(
                'odex_petty_cash.group_petty_cash_finance_admin'
            ):
                raise UserError(_('Only approved allocations can be posted.'))
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
            r.message_post(body=_('Allocation cancelled.'), subtype_xmlid='mail.mt_comment')

    def action_reset_draft(self):
        for r in self:
            if r.state in ('rejected', 'cancelled'):
                r.write({'state': 'draft'})
                r.message_post(body=_('Reset to Draft.'), subtype_xmlid='mail.mt_comment')

    def _create_journal_entry(self):
        """DR Employee Petty Cash GL / CR Cash Receipt Account"""
        self.ensure_one()
        acc = self.petty_cash_account_id
        journal = self.journal_id or acc.journal_id
        petty_gl = acc.account_id
        credit_gl = self.source_account_id or acc.cash_receipt_account_id

        if not journal:
            raise UserError(_("No journal. Configure in ODEX Petty Cash → Settings."))
        if not petty_gl:
            raise UserError(_("No Petty Cash GL Account on '%s'.") % acc.name)
        if not credit_gl:
            raise UserError(_(
                "No Cash Receipt Credit Account.\n"
                "Set it in ODEX Petty Cash → Settings → Cash Receipt Credit Account."
            ))

        partner_id = (
            acc.employee_id.address_home_id.id
            if acc.employee_id.address_home_id else False
        )
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'narration': self.notes or '',
            'line_ids': [
                (0, 0, {
                    'name': _('Cash Allocation to %s') % acc.employee_id.name,
                    'account_id': petty_gl.id,
                    'debit': self.amount, 'credit': 0.0,
                    'partner_id': partner_id,
                }),
                (0, 0, {
                    'name': _('Cash Allocation to %s') % acc.employee_id.name,
                    'account_id': credit_gl.id,
                    'debit': 0.0, 'credit': self.amount,
                    'partner_id': partner_id,
                }),
            ],
        })
        move.action_post()
        self.move_id = move.id

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
