from odoo import fields, models


class OdexCrmBusiness(models.Model):
    _name = "odex.crm.business"
    _description = "CRM Business Classification"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [("name_uniq", "unique(name)", "This business classification already exists.")]


class OdexCrmCustomerType(models.Model):
    _name = "odex.crm.customer.type"
    _description = "CRM Customer / Service Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [("name_uniq", "unique(name)", "This type already exists.")]
