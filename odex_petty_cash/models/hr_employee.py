# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    petty_cash_manager_id = fields.Many2one(
        'hr.employee', string='Petty Cash Manager',
        help="Approves this employee's petty cash expense requests.",
    )
    petty_cash_manager_user_id = fields.Many2one(
        'res.users', related='petty_cash_manager_id.user_id',
        string='Petty Cash Manager (User)', store=True,
    )
    petty_cash_account_id = fields.Many2one(
        'odex.petty.cash.account',
        compute='_compute_petty_cash_account', store=False,
        string='Petty Cash Account',
    )
    petty_cash_balance = fields.Monetary(
        compute='_compute_petty_cash_balance', store=False,
        currency_field='currency_id', string='Petty Cash Balance',
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
    )

    def _compute_petty_cash_account(self):
        for r in self:
            r.petty_cash_account_id = self.env['odex.petty.cash.account'].search(
                [('employee_id', '=', r.id), ('company_id', '=', self.env.company.id)], limit=1
            )

    def _compute_petty_cash_balance(self):
        for r in self:
            acc = self.env['odex.petty.cash.account'].search(
                [('employee_id', '=', r.id), ('company_id', '=', self.env.company.id)], limit=1
            )
            r.petty_cash_balance = acc.available_balance if acc else 0.0
