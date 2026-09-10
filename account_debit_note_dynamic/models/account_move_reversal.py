
from odoo import models, fields

class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    show_debit_note = fields.Boolean(
        default=lambda self: self.env.context.get('show_debit_note', False)
    )
