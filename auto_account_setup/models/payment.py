# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountPaymentNew(models.Model):
    _name = "account.payment.new"
    _inherits = {'account.move': 'move_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Payments"
    _order = "date desc, name desc"
    _check_company_auto = True


    def get_default_journal(self):
        r''' Retrieve the default journal for the account.payment.
        /!\ This method will not override the method in 'account.move' because the ORM
        doesn't allow overriding methods using _inherits. Then, this method will be called
        manually in 'create' and 'new'.
        :return: An account.journal record.
        '''
        journals = self.env['account.journal'].search([('type', '=', 'cash')], limit=1).id
        return journals

    # == Business fields ==
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry', required=True, readonly=True, ondelete='cascade',
        check_company=True)

    # qr_code = fields.Char(string="QR Code",
    #                       compute="_compute_qr_code",
    #                       help="QR-code report URL to use to generate the QR-code to scan with a banking app to perform this payment.")

    # == Synchronized fields with the account.move.lines ==
    amount = fields.Monetary(currency_field='currency_id')
    payment_type = fields.Selection([
        ('outbound', 'Send'),
        ('inbound', 'Receive'),
    ], string='Payment Type', default='outbound', required=True, tracking=True)
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], default='customer', tracking=True, required=True)
    payment_reference = fields.Char(string="Payment Reference", copy=False, tracking=True,
                                    help="Reference of the document used to issue this payment. Eg. check number, file name, etc.")
    currency_id = fields.Many2one('res.currency', string='Currency', store=True, readonly=False,
                                  compute='_compute_currency_id',
                                  help="The payment's currency.")
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer/Vendor",
        store=True, readonly=False, ondelete='restrict',
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        tracking=True,
        check_company=True)
    outstanding_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Outstanding Account",
        store=True,
        check_company=True)
    destination_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Destination Account',
        store=True, readonly=False,
        domain="[('user_type_id.type', 'in', ('receivable', 'payable')), ('company_id', '=', company_id)]",
        check_company=True)
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Destination Journal',
        domain="[('type', 'in', ('bank','cash')), ('company_id', '=', company_id)]",
        check_company=True,
        default=get_default_journal)

    amount_signed = fields.Monetary(
        currency_field='currency_id', compute='_compute_amount_signed', tracking=True,
        help='Negative value of amount field if payment_type is outbound')
    amount_company_currency_signed = fields.Monetary(
        currency_field='company_currency_id', compute='')
    setup_id = fields.Many2one('account.setup', string="Account Type", required=True,
                               help="Select Type for default debit and credit account setup.")
    # company_id = fields.Many2one('res.company', string='Company', required=True, help="Company",
    #                              default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        (
            'check_amount_not_negative',
            'CHECK(amount >= 0.0)',
            "The payment amount cannot be negative.",
        ),
    ]

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for pay in self:
            pay.currency_id = pay.journal_id.currency_id or pay.journal_id.company_id.currency_id


    @api.depends('amount_total_signed', 'payment_type')
    def _compute_amount_company_currency_signed(self):
        for payment in self:
            liquidity_lines = payment._seek_for_lines()[0]
            payment.amount_company_currency_signed = sum(liquidity_lines.mapped('balance'))

    @api.depends('amount', 'payment_type')
    def _compute_amount_signed(self):
        for payment in self:
            if payment.payment_type == 'outbound':
                payment.amount_signed = -payment.amount
            else:
                payment.amount_signed = payment.amount


    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.partner_type = 'customer'
            elif pay.payment_type == 'outbound':
                pay.partner_type = 'supplier'


    @api.depends('setup_id')
    @api.onchange('setup_id')
    def _onchange_setup_id(self):
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.outstanding_account_id = pay.setup_id.debit_account
                pay.destination_account_id = pay.setup_id.credit_account
            elif pay.payment_type == 'outbound':
                pay.outstanding_account_id = pay.setup_id.credit_account
                pay.destination_account_id = pay.setup_id.debit_account
            else:
                pay.outstanding_account_id = False
                pay.destination_account_id = False

    @api.depends('move_id.name')
    def name_get(self):
        return [(payment.id, payment.move_id.name != '/' and payment.move_id.name or _('Draft Payment')) for payment in self]

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        for i, pay in enumerate(payments):
            to_write = {
                'new_payment_id': pay.id,
                'journal_id':pay.journal_id.id,
                'partner_id':pay.partner_id.id,
                'setup_id':pay.setup_id.id
            }
            to_write['line_ids'] = [(0, 0, line_vals) for line_vals in pay.get_move_line_vals()]
            pay.move_id.write(to_write)
        return payments

    def _prepare_payment_display_name(self):
        '''
        Hook method for inherit
        When you want to set a new name for payment, you can extend this method
        '''
        return {
            'outbound-customer': _("Customer Reimbursement"),
            'inbound-customer': _("Customer Payment"),
            'outbound-supplier': _("Vendor Payment"),
            'inbound-supplier': _("Vendor Reimbursement"),
        }

    def get_move_line_vals(self):
        # NAME
        payment_display_name = self._prepare_payment_display_name()
        default_line_name = self.env['account.move.line']._get_default_line_name(
            payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
            self.amount,
            self.currency_id,
            self.date,
            partner=self.partner_id,
        )
        # AMOUNT
        write_off_amount_currency = 0.0

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = - self.amount
            write_off_amount_currency *= -1
        else:
            liquidity_amount_currency = write_off_amount_currency = 0.0

        write_off_balance = self.currency_id._convert(
            write_off_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance
        currency_id = self.currency_id.id
        line_vals_list = [
            # Liquidity line.
            {
                'name': default_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': self.currency_id.id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': default_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency,
                'currency_id': currency_id,
                'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]

        return line_vals_list


    def button_open_journal_entry(self):
        ''' Redirect the user to this payment journal.
        :return:    An action on account.move.
        '''
        self.ensure_one()
        return {
            'name': _("Journal Entry"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'context': {'create': False},
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }

    def action_post(self):
        ''' draft -> posted '''
        self.move_id._post(soft=False)

    def action_cancel(self):
        ''' draft -> cancelled '''
        self.move_id.button_cancel()

    def action_draft(self):
        ''' posted -> draft '''
        self.move_id.button_draft()
