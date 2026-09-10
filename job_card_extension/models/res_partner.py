# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # trn_no = fields.Char(string="TRN No")

    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', default=lambda self:self.env.user.company_id.country_id.id, tracking=True)
    vehicle_ids = fields.One2many("fleet.vehicle", "partner_id", string="Vehicle IDS")
    is_insurance = fields.Boolean(string="Is Insurance?")
    markup_spare_parts = fields.Float(
        string='Spare Parts Markup (%)',
        help='Percentage markup applied to spare parts for this customer.'
    )
    markup_labor = fields.Float(
        string='Labor Markup (%)',
        help='Percentage markup applied to labor charges for this customer.'
    )
    markup_sublet = fields.Float(
        string='Sublet Markup (%)',
        help='Percentage markup applied to sublet work for this customer.'
    )