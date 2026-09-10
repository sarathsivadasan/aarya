from odoo import fields, models

class ProjectTask(models.Model):
    _inherit = "project.task"

    proforma_invoice_ids = fields.Many2many(
        "account.move",
        string="Proforma Invoices",
        copy=False,
    )

    def action_create_proforma(self):
        self.ensure_one()

        action = self.show_invoice()

        ctx = eval(action.get('context', '{}'))
        ctx.update({
            'default_is_proforma': True,
        })

        action['context'] = ctx

        return action
