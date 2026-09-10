# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..services import constants

FIELD_KEY_SELECTION = [(key, constants.FIELD_LABELS[key])
                       for key in constants.MULKIYA_FIELDS]


class MulkiyaAlias(models.Model):
    """Data driven normalization table (section 27).

    Maps anything the OCR can produce - Arabic spellings, abbreviations,
    manufacturer variants, common OCR mistakes - onto the canonical value used
    for master data matching. Fully editable by a manager, so a new variant
    never requires a code change.
    """

    _name = 'odex.mulkiya.alias'
    _description = 'Mulkiya Value Alias'
    _order = 'field_key, source_value'

    field_key = fields.Selection(
        FIELD_KEY_SELECTION, string='Field',
        help="Leave empty to apply the alias to every field.")
    source_value = fields.Char(
        string='OCR Value', required=True,
        help="Value as produced by the OCR engine (Arabic or English).")
    target_value = fields.Char(
        string='Normalized Value', required=True,
        help="Canonical value used for display and master data matching.")
    active = fields.Boolean(default=True)
    note = fields.Char()

    _sql_constraints = [
        ('unique_alias', 'unique(field_key, source_value)',
         'This OCR value already has an alias for that field.'),
    ]

    @api.depends('source_value', 'target_value')
    def _compute_display_name(self):
        for alias in self:
            alias.display_name = '%s → %s' % (alias.source_value or '',
                                              alias.target_value or '')
