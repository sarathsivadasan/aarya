# -*- coding: utf-8 -*-

from odoo import models, fields

class setup(models.Model):
    _name = 'account.setup'


    name = fields.Char('Name', required=True, translate=True)
    debit_account = fields.Many2one(
        'account.account',
        string="Debit Account",
        required=True,
    )
    credit_account = fields.Many2one(
        'account.account',
        string="Credit Account",
        required=True,
    )
    journal_id = fields.Many2one('account.journal', string='Journal',
                                 required=True)



class AccountMove(models.Model):
    _inherit = "account.move"

    new_payment_id = fields.Many2one(
        index=True,
        comodel_name='account.payment.new',
        string="New Payment", copy=False, check_company=True)

    setup_id = fields.Many2one('account.setup', string="Account Type",
                                 help="Select Type for default debit and credit account setup.")
