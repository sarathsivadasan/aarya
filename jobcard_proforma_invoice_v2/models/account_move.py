from odoo import fields, models, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"

    is_proforma = fields.Boolean(string="Proforma Invoice", default=False)

    def action_post(self):
        for move in self:
            if move.is_proforma:
                raise ValidationError(
                    _("Proforma invoices cannot be posted. Create a Tax Invoice instead.")
                )
        return super().action_post()
