# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    job_id = fields.Many2one(String="project.task")
# class AccountPaymentRegister(models.TransientModel):
#     _inherit = 'account.payment.register'

#     register_no = fields.Char(string="Vehicle Number")

#     @api.onchange('line_ids')
#     @api.depends('line_ids')
#     def onchange_line_ids(self):
#         """
#         Update vehicle number
#         """
#         for rec in self:
#             if rec.line_ids:
#                 move_id = rec.line_ids.mapped("move_id")[0]
#                 if move_id:
#                     rec.register_no = move_id.cc_registration_no

