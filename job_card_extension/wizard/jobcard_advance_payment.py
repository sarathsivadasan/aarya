# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from werkzeug.urls import url_encode

_logger = logging.getLogger(__name__)


class JobcardAdvancePayment(models.TransientModel):

    _name = "jobcard.advance.payment.wizard"
    _description = "Jobcard Advance Payment Wizard"

    job_id = fields.Many2one('project.task','Jobcard')
    payment_type = fields.Selection([
        ('outbound', 'Send Money'),
        ('inbound', 'Receive Money'),
    ], string='Payment Type', store=True, copy=False, default='inbound')
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], store=True, copy=False, default='customer')
    partner_id = fields.Many2one('res.partner', string="Partner", related="job_id.partner_id")
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=True, required=True)
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)
    communication = fields.Char(string='Memo',)
    bank_reference = fields.Char(string='Bank Reference')
    # == Payment methods fields ==
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method',
        readonly=False, store=True,
        compute='_compute_payment_method_line_id',
        domain="[('id', 'in', available_payment_method_line_ids)]",
        help="Manual: Pay or Get paid by any method outside of Odoo.\n"
        "Payment Acquirers: Each payment acquirer has its own Payment Method. Request a transaction on/to a card thanks to a payment token saved by the partner when buying or subscribing online.\n"
        "Check: Pay bills by check and print it from Odoo.\n"
        "Batch Deposit: Collect several customer checks at once generating and submitting a batch deposit to your bank. Module account_batch_payment is necessary.\n"
        "SEPA Credit Transfer: Pay in the SEPA zone by submitting a SEPA Credit Transfer file to your bank. Module account_sepa is necessary.\n"
        "SEPA Direct Debit: Get paid in the SEPA zone thanks to a mandate your partner will have granted to you. Module account_sepa is necessary.\n")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line', compute='_compute_payment_method_line_fields')
    hide_payment_method_line = fields.Boolean(
        compute='_compute_payment_method_line_fields',
        help="Technical field used to hide the payment method if the selected journal has only one available which is 'manual'")

    @api.depends('payment_type', 'journal_id', 'currency_id')
    def _compute_payment_method_line_fields(self):
        for wizard in self:
            wizard.available_payment_method_line_ids = wizard.journal_id._get_available_payment_method_lines(wizard.payment_type)
            if wizard.payment_method_line_id.id not in wizard.available_payment_method_line_ids.ids:
                # In some cases, we could be linked to a payment method line that has been unlinked from the journal.
                # In such cases, we want to show it on the payment.
                wizard.hide_payment_method_line = False
            else:
                wizard.hide_payment_method_line = len(wizard.available_payment_method_line_ids) == 1 \
                                                  and wizard.available_payment_method_line_ids.code == 'manual'

    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_line_id(self):
        for wizard in self:
            available_payment_method_lines = wizard.journal_id._get_available_payment_method_lines(wizard.payment_type)

            # Select the first available one by default.
            if available_payment_method_lines:
                wizard.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                wizard.payment_method_line_id = False

    def generate_advance_payment(self):
        self.ensure_one()
        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'memo': self.communication,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            # 'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'job_id': self.job_id.id,
            # 'destination_account_id': self.line_ids[0].account_id.id,
            # 'write_off_line_vals': [],
        }
        payments = self.env['account.payment'].create(payment_vals)
        payments.action_post()
        return payments
        # for batch_id in self.batch_id:
        #     for payslip_lines in batch_id.slip_ids:
        #         if not payslip_lines.employee_id.address_home_id:
        #             raise ValidationError(_('Please Define Employee Private Address'))

        #     for payslip in batch_id.slip_ids:
        #         if payslip.state == 'done':
        #             total_amount = payslip.line_ids.filtered(lambda x: x.salary_rule_id.code == 'NET').amount
        #             payment_values = {
        #                 'partner_type': 'supplier',
        #                 'payment_type': 'outbound',
        #                 'partner_id': payslip.employee_id.address_home_id.id,
        #                 'journal_id': self.journal_id.id,
        #                 'company_id': self.company_id.id,
        #                 'payment_method_id': self.payment_method_line_id.id,
        #                 'amount': total_amount,
        #                 'currency_id': self.currency_id.id,
        #                 'date': self.payment_date,
        #                 'ref': self.communication,
        #                 'payslip_id': payslip.id
        #             }

        #             # Create payment and post it
        #             payment = self.env['account.payment'].create(payment_values)
        #             payment.action_post()
        #             # move_line_ids = payslip.move_id.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable') and not line.reconciled)
        #             # for line in move_line_ids:
        #             #     to_reconcile_line = payment.move_id.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable') and not line.reconciled)
        #             #     (line + to_reconcile_line).reconcile()
        #             payslip.write({'state': 'paid'})
        #             # for move in payment.move_line_ids:
        #             #     move.name = +
        #             # Log the payment in the chatter
        #             # body = (_("A payment of %s %s with the reference <a href='/mail/view?%s'>%s</a> related to your expense %s has been made.") % (payment.amount, payment.currency_id.symbol, url_encode({'model': 'account.payment', 'res_id': payment.id}), payment.name, payslip.name))
        #             # payslip.message_post(body=body)

        #             # Reconcile the payment and the expense, i.e. lookup on the payable account move lines
        #             # account_move_lines_to_reconcile = self.env['account.move.line']
        #             # for line in payment.line_ids + payslip.move_id.line_ids:
        #             #     if line.account_id.internal_type == 'payable':
        #             #         account_move_lines_to_reconcile |= line
        #             # account_move_lines_to_reconcile.reconcile()
        #         payslip_paid_search = self.env['hr.payslip'].search([('payslip_run_id','=', batch_id.id),('state','=','paid')])
        #         if payslip_paid_search:
        #             if len(batch_id.slip_ids) == len(payslip_paid_search):
        #                 self.batch_id.write({'state':'paid'})

        return {'type': 'ir.actions.act_window_close'}