from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    count_sale_ids = fields.Integer(string="Count Sales", compute="_count_sale_ids")
    sale_ids = fields.One2many("sale.order", "vehicle_id", string="Sale IDS")

    @api.depends('sale_ids')
    def _count_sale_ids(self):
        for rec in self:
            rec.count_sale_ids = len(rec.sale_ids)

    def action_sales_list(self):
        return {
            'name': ('Sale order'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'context': {},
            'domain': [('id', 'in', self.sale_ids.ids)],
            'target': 'current',
            'type': 'ir.actions.act_window',
        }
