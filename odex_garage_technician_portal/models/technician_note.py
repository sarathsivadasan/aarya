# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class TechnicianNote(models.Model):
    _name = 'technician.note'
    _description = 'Technician Timestamped Note'
    _order = 'create_date desc'

    task_id = fields.Many2one('project.task', string='Job Card',
                               required=True, ondelete='cascade', index=True)
    content = fields.Html(string='Note', required=True, sanitize=True)
    user_id = fields.Many2one('res.users', string='User',
                               default=lambda self: self.env.user, required=True)
    note_date = fields.Datetime(string='Date/Time', default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.task_id:
                rec.task_id._add_log('Notes Added', _('A note was added.'))
        return records
