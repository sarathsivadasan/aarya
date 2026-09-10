# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..services import constants

FIELD_KEY_SELECTION = [(key, constants.FIELD_LABELS[key])
                       for key in constants.MULKIYA_FIELDS]


class MulkiyaMatchRule(models.Model):
    """Configurable link between an OCR field and an Odoo master model.

    Nothing about Fleet is hard-coded in the python code: the default rules are
    shipped as data and every one of them is silently ignored when the target
    model is not installed. This is what keeps the application standalone
    (sections 20 and 31).
    """

    _name = 'odex.mulkiya.match.rule'
    _description = 'Mulkiya Master Data Matching Rule'
    _order = 'field_key, sequence, id'

    sequence = fields.Integer(default=10)
    field_key = fields.Selection(FIELD_KEY_SELECTION, string='OCR Field',
                                 required=True, index=True)
    model_name = fields.Char(
        string='Target Model', required=True,
        help="Technical name of the Odoo model to match against, e.g. "
             "fleet.vehicle.model.brand. Ignored when the model is not installed.")
    search_field = fields.Char(
        string='Search Field', default='name', required=True,
        help="Field of the target model compared with the OCR value.")
    extra_domain = fields.Char(
        string='Extra Domain',
        help="Optional additional domain. The OCR value is available as 'value'.")
    parent_field_key = fields.Selection(
        FIELD_KEY_SELECTION, string='Depends On',
        help="Restrict the search using another already matched field, "
             "for example match the Model only inside the matched Make.")
    parent_relation_field = fields.Char(
        string='Parent Field',
        help="Many2one field of the target model pointing at the parent record, "
             "for example brand_id on fleet.vehicle.model.")
    parent_required = fields.Boolean(
        string='Parent Mandatory', default=False,
        help="When set, no match is returned if the parent could not be matched.")
    model_available = fields.Boolean(string='Installed',
                                     compute='_compute_model_available')
    active = fields.Boolean(default=True)

    @api.depends('model_name')
    def _compute_model_available(self):
        for rule in self:
            rule.model_available = bool(rule.model_name) and \
                rule.model_name in self.env

    @api.depends('field_key', 'model_name')
    def _compute_display_name(self):
        labels = dict(FIELD_KEY_SELECTION)
        for rule in self:
            rule.display_name = '%s → %s' % (labels.get(rule.field_key, ''),
                                             rule.model_name or '')
