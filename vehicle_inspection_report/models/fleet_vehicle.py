from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    count_inspection = fields.Integer(string="Count Inspection", compute="_count_vehicle_inspection")
    
    def _count_vehicle_inspection(self):
        for rec in self:
            vehicle_inspection = self.env['project.task'].search([('vehicle_id', '=', rec.id), ('is_vc', '=', True)])
            rec.count_inspection = len(vehicle_inspection.ids)
    
    def action_vehicle_inspection_list(self):
        inspection_form = self.env.ref('vehicle_inspection_report.view_form_v_job_card_extension', False)
        inspection_tree = self.env.ref('vehicle_inspection_report.view_tree_v_job_card_extension', False)
        return {
            'name': ('Vehicle Inspection'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'views': [[inspection_tree.id, 'list'], [inspection_form.id, 'form']],
            'context': {},
            'domain': [('vehicle_id', '=', self.id), ('is_vc', '=', True)],
            'target': 'current',
            'type': 'ir.actions.act_window',
        }
