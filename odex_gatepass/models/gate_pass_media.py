# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GatePassImage(models.Model):
    _name = 'fleet.gate.pass.image'
    _description = "Gate Pass Vehicle Image"
    _order = 'sequence, id'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    image_type = fields.Selection([
        ('front', 'Front View'),
        ('rear', 'Rear View'),
        ('left', 'Left Side'),
        ('right', 'Right Side'),
        ('interior', 'Interior'),
        ('engine', 'Engine Bay'),
        ('dashboard', 'Dashboard'),
        ('odometer', 'Odometer'),
        ('damage', 'Damage'),
        ('additional', 'Additional')],
        required=True, default='additional')
    image = fields.Image(required=True, max_width=1920, max_height=1920)
    name = fields.Char(compute="_compute_name")

    @api.depends('image_type')
    def _compute_name(self):
        for rec in self:
            rec.name = dict(
                rec._fields['image_type']._description_selection(self.env)
            ).get(rec.image_type)


class GatePassDamage(models.Model):
    _name = 'fleet.gate.pass.damage'
    _description = "Gate Pass Damage Marker"
    _order = 'id'

    gate_pass_id = fields.Many2one(
        'fleet.gate.pass', required=True, ondelete='cascade', index=True)
    view_side = fields.Selection([
        ('front', 'Front'),
        ('rear', 'Rear'),
        ('left', 'Left'),
        ('right', 'Right'),
        ('top', 'Top')],
        string="View", required=True, default='top')
    pos_x = fields.Float(string="X %", help="Horizontal position, 0-100")
    pos_y = fields.Float(string="Y %", help="Vertical position, 0-100")
    damage_type = fields.Selection([
        ('scratch', 'Scratch'),
        ('dent', 'Dent'),
        ('broken', 'Broken'),
        ('glass', 'Glass'),
        ('paint', 'Paint')],
        required=True, default='scratch')
    severity = fields.Selection([
        ('minor', 'Minor'),
        ('major', 'Major')],
        required=True, default='minor')
    note = fields.Char()
