# -*- coding: utf-8 -*-

import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class GatePass(models.Model):
    _inherit = 'project.task'

    entries_count = fields.Integer(
        string="Entries",
        compute="_compute_journal_entries"
    )

    def _compute_journal_entries(self):
        Move  = self.env['account.move']
        for rec in self:
            entries_count = 0
            if rec.use_coupon:
                entries_count = Move.search([
                     ('coupon_id', '=', rec.customer_coupon_id.id),
                ])
                move_names = Move.mapped('name')
                same_name_ref_moves = Move.search([
                    '|',('ref', 'in',move_names),
                    ('name', '=',move_names),
                ])

                entries_count = len((entries_count | same_name_ref_moves))

            rec.entries_count = entries_count

    def action_view_entries(self):
        self.ensure_one()

        if not self.use_coupon or not self.customer_coupon_id:
            return False

        Move = self.env['account.move']

        coupon_moves = Move.search([
            ('coupon_id', '=', self.customer_coupon_id.id),
        ])

        move_names = coupon_moves.mapped('name')

        same_name_ref_moves = Move.search([
            ('ref', 'in', move_names)
        ])
        all_moves = coupon_moves | same_name_ref_moves

        return {
            'type': 'ir.actions.act_window',
            'name': _('Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_moves.ids)],
        }