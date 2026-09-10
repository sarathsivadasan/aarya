# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CouponPaymentWizard(models.TransientModel):
    _name = 'coupon.payment.wizard'
    _description = 'Coupon Payment Wizard'

    coupon_id = fields.Many2one(
        'customer.coupon', string='Coupon', required=True,
        readonly=True,
    )
    customer_id = fields.Many2one(
        'res.partner', string='Customer',
        related='coupon_id.customer_id',
    )
    currency_id = fields.Many2one(
        'res.currency', related='coupon_id.currency_id',
    )
    coupon_amount = fields.Monetary(
        related='coupon_id.coupon_amount', string='Coupon Amount',
    )
    total_paid = fields.Monetary(
        related='coupon_id.total_paid_amount', string='Already Paid',
    )
    balance_amount = fields.Monetary(
        related='coupon_id.balance_amount', string='Balance',
    )

    payment_date = fields.Date(
        string='Payment Date', default=fields.Date.today, required=True,
    )
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank/Card'),
        ('pdc', 'PDC'),
    ], string='Payment Method', required=True, default='cash')

    payment_type = fields.Selection([
        ('regular', 'Regular'),
        ('pdc', 'PDC'),
    ], default='regular', required=True)

    journal_id = fields.Many2one(
        'account.journal', string='Journal', required=True,
        domain="[('type', 'in', ['cash', 'bank'])]",
    )
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id', required=True,
    )
    reference = fields.Char(string='Reference / Memo')

    # PDC
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    bank_name = fields.Char(string='Bank Name')

    notes = fields.Text(string='Notes')

    @api.onchange('payment_method')
    def _onchange_payment_method(self):
        jtype = 'cash' if self.payment_method == 'cash' else 'bank'
        journal = self.env['account.journal'].search([('type', '=', jtype)], limit=1)
        self.journal_id = journal
        self.payment_type = 'pdc' if self.payment_method == 'pdc' else 'regular'

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))

    def action_register_payment(self):
        self.ensure_one()
        coupon = self.coupon_id
        if coupon.state not in ('confirmed', 'posted', 'partially_used'):
            raise UserError(_('Coupon must be in Confirmed or Posted state to accept payments.'))

        payment = self.env['customer.coupon.payment'].create({
            'coupon_id': coupon.id,
            'payment_date': self.payment_date,
            'payment_method': self.payment_method,
            'payment_type': self.payment_type,
            'journal_id': self.journal_id.id,
            'amount': self.amount,
            'reference': self.reference or '',
            'cheque_number': self.cheque_number or '',
            'cheque_date': self.cheque_date,
            'bank_name': self.bank_name or '',
            'notes': self.notes or '',
        })
        payment.action_post()
        return {'type': 'ir.actions.act_window_close'}
