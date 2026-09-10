# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from odoo.addons.odex_mulkiya_scan.services import constants


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    mulkiya_scan_ids = fields.One2many('odex.mulkiya.scan', 'vehicle_id',
                                       string='Mulkiya Scans')
    mulkiya_scan_count = fields.Integer(compute='_compute_mulkiya_scan_count')

    @api.depends('mulkiya_scan_ids')
    def _compute_mulkiya_scan_count(self):
        data = self.env['odex.mulkiya.scan']._read_group(
            [('vehicle_id', 'in', self.ids)], ['vehicle_id'], ['__count'])
        mapped = {vehicle.id: count for vehicle, count in data}
        for vehicle in self:
            vehicle.mulkiya_scan_count = mapped.get(vehicle.id, 0)

    def action_scan_mulkiya(self):
        """Open the Mulkiya scanner for this vehicle in a dialog."""
        self.ensure_one()
        scan = self.env['odex.mulkiya.scan'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', [constants.STATE_DRAFT, constants.STATE_UPLOADED,
                             constants.STATE_EXTRACTED]),
        ], limit=1, order='create_date desc')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scan Mulkiya (OCR)'),
            'res_model': 'odex.mulkiya.scan',
            'res_id': scan.id or False,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'odex_mulkiya_scan_fleet.view_mulkiya_scan_form_dialog').id,
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_source_reference': '%s,%s' % (self._name, self.id),
                'dialog_size': 'extra-large',
            },
        }

    def action_open_mulkiya_scans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mulkiya Scans'),
            'res_model': 'odex.mulkiya.scan',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
