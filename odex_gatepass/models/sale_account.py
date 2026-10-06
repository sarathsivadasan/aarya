# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', string="Gate Pass", index=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders.filtered('gate_pass_id'):
            order.gate_pass_id._log_timeline('estimate')
        return orders

    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered('gate_pass_id'):
            order.gate_pass_id._log_timeline('approval')
        return res

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.gate_pass_id:
            vals['gate_pass_id'] = self.gate_pass_id.id
        return vals


class AccountMove(models.Model):
    _inherit = 'account.move'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', string="Gate Pass", index=True, copy=False)

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        for move in posted.filtered(
                lambda m: m.gate_pass_id and m.move_type == 'out_invoice'):
            move.gate_pass_id._log_timeline('invoice')
        return posted

    def write(self, vals):
        res = super().write(vals)
        if 'payment_state' in vals:
            for move in self.filtered(
                    lambda m: m.gate_pass_id
                    and m.move_type == 'out_invoice'
                    and m.payment_state in ('paid', 'in_payment')):
                move.gate_pass_id._log_timeline('payment')
        return res
