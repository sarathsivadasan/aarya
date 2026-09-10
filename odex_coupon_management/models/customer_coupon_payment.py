# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CustomerCouponPayment(models.Model):
    _name = 'customer.coupon.payment'
    _description = 'Customer Coupon Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Reference', readonly=True, copy=False, default='New',
    )
    coupon_id = fields.Many2one(
        'customer.coupon', string='Customer Coupon',
        required=True, ondelete='cascade',
    )
    customer_id = fields.Many2one(
        'res.partner', string='Customer',
        related='coupon_id.customer_id', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='coupon_id.currency_id', store=True,
    )
    payment_date = fields.Date(
        string='Payment Date', default=fields.Date.today,
        required=True, tracking=True,
    )
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank/Card'),
        ('pdc', 'PDC'),
    ], string='Payment Method', required=True, default='cash', tracking=True)

    payment_type = fields.Selection([
        ('regular', 'Regular'),
        ('pdc', 'PDC'),
    ], string='Payment Type', required=True, default='regular')

    journal_id = fields.Many2one(
        'account.journal', string='Journal', required=True,
        domain="[('type', 'in', ['cash', 'bank'])]",
    )
    reference = fields.Char(string='Reference', tracking=True)

    # PDC specific
    cheque_date = fields.Date(string='Cheque Date')
    cheque_number = fields.Char(string='Cheque Number')
    bank_name = fields.Char(string='Bank Name')

    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
        required=True, tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    move_id = fields.Many2one(
        'account.move', string='Journal Entry', readonly=True,
    )
    notes = fields.Text(string='Notes')

    pdc_payment_id = fields.Many2one(
        'pdc.account.payment',
        string='PDC Payment',
        readonly=True,
        copy=False,
    )

    # ── CRUD ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('customer.coupon.payment') or 'New'
                )
        return super().create(vals_list)

    # ── Onchange ──────────────────────────────────────────────────────────

    @api.onchange('payment_method')
    def _onchange_payment_method(self):
        jtype = 'cash' if self.payment_method == 'cash' else 'bank'
        journal = self.env['account.journal'].search([('type', '=', jtype)], limit=1)
        self.journal_id = journal
        self.payment_type = 'pdc' if self.payment_method == 'pdc' else 'regular'

    # ── Constraints ───────────────────────────────────────────────────────

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))

    # ── Actions ───────────────────────────────────────────────────────────

    # def action_post(self):
    #     for rec in self:
    #         if rec.state != 'draft':
    #             raise UserError(_('Only draft payments can be posted.'))
    #         move = rec.coupon_id.action_create_accounting_entry(rec)
    #         rec.move_id = move
    #         rec.state = 'posted'
    #         # Auto-advance coupon state
    #         coupon = rec.coupon_id
    #         if coupon.state == 'confirmed':
    #             coupon.state = 'posted'
    #         rec.message_post(
    #             body=_('Payment posted. Journal Entry: <a href="#">%s</a>') % move.name
    #         )

    # def action_post(self):
    #     for rec in self:
    #         if rec.state != 'draft':
    #             raise UserError(_('Only draft payments can be posted.'))
    #
    #         # Create PDC record
    #         if rec.payment_method == 'pdc':
    #             pdc_payment = self.env['pdc.account.payment'].create({
    #                 'partner_id': rec.customer_id.id,
    #                 'partner_type': 'customer',
    #                 'payment_type': 'inbound',
    #                 'amount': rec.amount,
    #                 'currency_id': rec.currency_id.id,
    #                 'payment_date': rec.payment_date,
    #                 'due_date': rec.cheque_date,
    #                 'cheque_reference': rec.cheque_number,
    #                 'bank': rec.bank_name,
    #                 'journal_id': rec.journal_id.id,
    #                 'communication': rec.reference or rec.name,
    #             })
    #
    #             # pdc_payment.post()
    #
    #             pdc_payment.post()  # or validate_pdc_payment()
    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft payments can be posted.'))

            if rec.payment_method == 'pdc':

                if not rec.cheque_date:
                    raise UserError(_("Please enter Cheque Date."))

                pdc_payment = self.env['pdc.account.payment'].create({
                    'partner_id': rec.customer_id.id,
                    'partner_type': 'customer',
                    'payment_type': 'inbound',
                    'amount': rec.amount,
                    'currency_id': rec.currency_id.id,
                    'payment_date': rec.payment_date,
                    'due_date': rec.cheque_date,
                    'cheque_reference': rec.cheque_number,
                    'bank': rec.bank_name,
                    'journal_id': rec.journal_id.id,
                    'communication': rec.reference or rec.name,
                })

                pdc_payment.post()

            move = rec.coupon_id.action_create_accounting_entry(rec)

            rec.write({
                'move_id': move.id,
                'state': 'posted',
            })
    def action_cancel(self):
        for rec in self:
            if rec.state == 'posted' and rec.move_id:
                if rec.move_id.state == 'posted':
                    rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = 'cancelled'
            rec.message_post(body=_('Payment cancelled.'))

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'cancelled':
                rec.state = 'draft'
