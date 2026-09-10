# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TechnicianPartPhoto(models.Model):
    _name = 'technician.part.photo'
    _description = 'Technician Part Photo'
    _order = 'create_date desc'

    task_id = fields.Many2one('project.task', string='Job / Inspection',
                               required=True, ondelete='cascade', index=True)
    part_reference = fields.Char(
        string='Part / Product',
        help='Freeform label for which part this photo documents, e.g. '
             'the product name or a request number.')
    image = fields.Image(string='Photo', required=True, max_width=1600, max_height=1600)
    description = fields.Text(string='Description')
    user_id = fields.Many2one('res.users', string='Uploaded By',
                               default=lambda self: self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.task_id:
                rec.task_id._add_log(
                    'Photo Uploaded',
                    'Part photo added%s.' % (
                        ' (%s)' % rec.part_reference if rec.part_reference else ''))
        return records
