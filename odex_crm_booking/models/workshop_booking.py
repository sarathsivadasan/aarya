from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

class WorkshopBooking(models.Model):
    _inherit = 'odex.workshop.booking'

    crm_id = fields.Many2one('crm.lead', string="CRM")