from odoo import models
from odoo.tools.safe_eval import safe_eval


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_reverse(self):
        action = super().action_reverse()

        if self.move_type in ('in_invoice', 'in_refund'):
            ctx = action.get('context', {})

            if isinstance(ctx, str):
                ctx = safe_eval(ctx)

            ctx['show_debit_note'] = True
            action['context'] = ctx

        return action