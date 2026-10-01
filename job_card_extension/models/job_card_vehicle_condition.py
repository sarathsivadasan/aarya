# -*- coding: utf-8 -*-
"""Vehicle photos (technician-portal style capture slots) and damage
marking (gate-pass style map) for job cards (project.task / is_jobcard)."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Same slot sheet as the technician portal / gate pass Photos tab.
PHOTO_TYPES = [
    ('front', 'Front'),
    ('rear', 'Rear'),
    ('left', 'Left Side'),
    ('right', 'Right Side'),
    ('top', 'Top View'),
    ('front_left', 'Front-Left Corner'),
    ('front_right', 'Front-Right Corner'),
    ('rear_left', 'Rear-Left Corner'),
    ('rear_right', 'Rear-Right Corner'),
    ('damage', 'Any visible dent, scratch, or damage'),
    ('odometer', 'Odometer Reading'),
    ('additional', 'Additional Photo'),
]
PHOTO_KEYS = [k for k, _l in PHOTO_TYPES]

# Same legend as the gate pass damage map.
DAMAGE_TYPES = [
    ('dent', 'Dent'),
    ('scratch', 'Scratch'),
    ('scuff', 'Scuff'),
    ('crack', 'Crack'),
    ('bent', 'Bent'),
    ('paint', 'Paint'),
    ('missing', 'Missing'),
    ('replaced', 'Replaced'),
]
DAMAGE_CODES = {
    'dent': 'D', 'scratch': 'S', 'scuff': 'Sc', 'crack': 'C',
    'bent': 'B', 'paint': 'P', 'missing': 'M', 'replaced': 'R',
}
DAMAGE_COLORS = {
    'dent': '#e53935', 'scratch': '#fb8c00', 'scuff': '#fdd835',
    'crack': '#8e24aa', 'bent': '#3949ab', 'paint': '#00897b',
    'missing': '#424242', 'replaced': '#43a047',
}


class JobCardVehiclePhoto(models.Model):
    _name = 'job.card.vehicle.photo'
    _description = 'Job Card Vehicle Photo'
    _order = 'task_id, sequence, id'

    task_id = fields.Many2one('project.task', string='Job Card', required=True,
                              ondelete='cascade', index=True)
    photo_type = fields.Selection(PHOTO_TYPES, string='Angle', required=True,
                                  default='additional')
    sequence = fields.Integer(compute='_compute_sequence', store=True)
    image = fields.Image(string='Photo', max_width=1920, max_height=1920,
                         required=True, attachment=True)
    image_256 = fields.Image(related='image', max_width=256, max_height=256,
                             store=True, string='Thumbnail')
    caption = fields.Char(string='Description')
    captured_by = fields.Many2one('res.users', string='Captured By',
                                  default=lambda self: self.env.user, readonly=True)
    captured_on = fields.Datetime(string='Captured On', default=fields.Datetime.now,
                                  readonly=True)

    @api.depends('photo_type')
    def _compute_sequence(self):
        for rec in self:
            rec.sequence = PHOTO_KEYS.index(rec.photo_type) if rec.photo_type in PHOTO_KEYS else 99

    @api.depends('photo_type', 'task_id')
    def _compute_display_name(self):
        labels = dict(PHOTO_TYPES)
        for rec in self:
            rec.display_name = '%s - %s' % (rec.task_id.name or '', labels.get(rec.photo_type, ''))


class JobCardDamage(models.Model):
    _name = 'job.card.damage'
    _description = 'Job Card Damage Marker'
    _order = 'task_id, id'

    task_id = fields.Many2one('project.task', string='Job Card', required=True,
                              ondelete='cascade', index=True)
    damage_type = fields.Selection(DAMAGE_TYPES, string='Type', required=True, default='dent')
    code = fields.Char(compute='_compute_code_color', store=True)
    color = fields.Char(compute='_compute_code_color', store=True)
    severity = fields.Selection([('minor', 'Minor'), ('major', 'Major')],
                                string='Severity', required=True, default='minor')
    pos_x = fields.Float(string='X (%)', digits=(5, 2))
    pos_y = fields.Float(string='Y (%)', digits=(5, 2))
    note = fields.Char(string='Note')
    marked_by = fields.Many2one('res.users', string='Marked By',
                                default=lambda self: self.env.user, readonly=True)

    @api.depends('damage_type')
    def _compute_code_color(self):
        for rec in self:
            rec.code = DAMAGE_CODES.get(rec.damage_type, '?')
            rec.color = DAMAGE_COLORS.get(rec.damage_type, '#757575')

    @api.constrains('pos_x', 'pos_y')
    def _check_position(self):
        for rec in self:
            if not (0 <= rec.pos_x <= 100 and 0 <= rec.pos_y <= 100):
                raise ValidationError(_('Damage marker position must be within the vehicle image.'))

    @api.depends('damage_type', 'severity')
    def _compute_display_name(self):
        types = dict(DAMAGE_TYPES)
        for rec in self:
            rec.display_name = '%s (%s)' % (types.get(rec.damage_type, ''), rec.severity or '')


class ProjectTaskVehicleCondition(models.Model):
    _inherit = 'project.task'

    vehicle_photo_ids = fields.One2many('job.card.vehicle.photo', 'task_id',
                                        string='Vehicle Photos')
    damage_ids = fields.One2many('job.card.damage', 'task_id', string='Damage Marks')
    vehicle_photo_count = fields.Integer(compute='_compute_condition_counts')
    damage_count = fields.Integer(compute='_compute_condition_counts')
    major_damage_count = fields.Integer(compute='_compute_condition_counts')

    @api.depends('vehicle_photo_ids', 'damage_ids', 'damage_ids.severity')
    def _compute_condition_counts(self):
        for rec in self:
            rec.vehicle_photo_count = len(rec.vehicle_photo_ids)
            rec.damage_count = len(rec.damage_ids)
            rec.major_damage_count = len(rec.damage_ids.filtered(lambda d: d.severity == 'major'))

    # ------------------------------------------------------------------
    # Import from gate pass (runtime-probed, no hard dependency)
    # ------------------------------------------------------------------
    _GP_MODELS = ['odex.gate.pass', 'fleet.gate.pass']

    @staticmethod
    def _first_field(model, names):
        for n in names:
            if n in model._fields:
                return n
        return False

    def _find_gate_pass(self):
        self.ensure_one()
        if not self.vehicle_id:
            return False
        for gp_name in self._GP_MODELS:
            if gp_name not in self.env:
                continue
            GP = self.env[gp_name].sudo()
            if 'vehicle_id' not in GP._fields:
                continue
            gp = GP.search([('vehicle_id', '=', self.vehicle_id.id)],
                           order='create_date desc, id desc', limit=1)
            if gp:
                return gp
        return False

    def _gp_children(self, gp, suffixes):
        """Return records of <gp model>.<suffix> linked to gp via any m2o."""
        for suffix in suffixes:
            name = '%s.%s' % (gp._name, suffix)
            if name not in self.env:
                continue
            Child = self.env[name].sudo()
            link = next((f for f, fld in Child._fields.items()
                         if fld.type == 'many2one' and fld.comodel_name == gp._name), False)
            if link:
                return Child.search([(link, '=', gp.id)])
        return []

    @staticmethod
    def _match_key(value, keys, default):
        val = (value or '').lower()
        if val in keys:
            return val
        for k in keys:
            if k in val or (val and val in k):
                return k
        return default

    def action_import_gate_pass_condition(self):
        self.ensure_one()
        gp = self._find_gate_pass()
        if not gp:
            raise UserError(_('No gate pass found for this vehicle.'))
        dmg_keys = [k for k, _l in DAMAGE_TYPES]
        n_dmg = n_photo = 0

        if not self.damage_ids:
            for d in self._gp_children(gp, ['damage']):
                fx = self._first_field(d, ['pos_x', 'x', 'x_percent', 'position_x'])
                fy = self._first_field(d, ['pos_y', 'y', 'y_percent', 'position_y'])
                if not fx or not fy:
                    break
                ft = self._first_field(d, ['damage_type', 'type'])
                fs = self._first_field(d, ['severity'])
                fn = self._first_field(d, ['note', 'description', 'remarks', 'name'])
                sev = (d[fs] or 'minor') if fs else 'minor'
                self.env['job.card.damage'].create({
                    'task_id': self.id,
                    'damage_type': self._match_key(d[ft] if ft else '', dmg_keys, 'dent'),
                    'severity': 'major' if 'major' in str(sev).lower() else 'minor',
                    'pos_x': min(max(float(d[fx] or 0), 0), 100),
                    'pos_y': min(max(float(d[fy] or 0), 0), 100),
                    'note': (d[fn] or '') if fn else '',
                })
                n_dmg += 1

        if not self.vehicle_photo_ids:
            for p in self._gp_children(gp, ['photo', 'image']):
                fi = self._first_field(p, ['image', 'image_1920', 'photo', 'datas'])
                if not fi or not p[fi]:
                    continue
                ft = self._first_field(p, ['photo_type', 'image_type', 'type'])
                fc = self._first_field(p, ['caption', 'description', 'name'])
                self.env['job.card.vehicle.photo'].create({
                    'task_id': self.id,
                    'photo_type': self._match_key(p[ft] if ft else '', PHOTO_KEYS, 'additional'),
                    'image': p[fi],
                    'caption': (p[fc] or '') if fc else '',
                })
                n_photo += 1

        self.message_post(body=_('Imported %(d)s damage mark(s) and %(p)s photo(s) from gate pass %(gp)s.',
                                 d=n_dmg, p=n_photo, gp=gp.display_name))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Gate Pass Import'),
                'message': _('%(d)s damage mark(s), %(p)s photo(s) imported from %(gp)s.',
                             d=n_dmg, p=n_photo, gp=gp.display_name),
                'type': 'success' if (n_dmg or n_photo) else 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
