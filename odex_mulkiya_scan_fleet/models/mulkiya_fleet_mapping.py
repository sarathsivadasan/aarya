# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.odex_mulkiya_scan.services import constants

_logger = logging.getLogger(__name__)

FIELD_KEY_SELECTION = [(key, constants.FIELD_LABELS[key])
                       for key in constants.MULKIYA_FIELDS]


class MulkiyaFleetMapping(models.Model):
    """Configurable mapping between an OCR field and a fleet.vehicle field.

    Nothing is hard-coded: every target field is checked against the live
    ``fleet.vehicle`` definition, so a customised Fleet (extra emirate,
    plate-code or colour models) only needs a configuration change here.
    """

    _name = 'odex.mulkiya.fleet.mapping'
    _description = 'Mulkiya to Fleet Field Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    field_key = fields.Selection(FIELD_KEY_SELECTION, string='OCR Field',
                                 required=True, index=True)
    field_name = fields.Char(
        string='Vehicle Field', required=True,
        help="Technical field name on fleet.vehicle, e.g. vin_sn or model_id. "
             "Mappings pointing at a field that does not exist are skipped.")
    use_matched_record = fields.Boolean(
        string='Use Matched Record', default=False,
        help="For relational fields: write the master record matched during "
             "the scan instead of the raw text value.")
    overwrite = fields.Boolean(
        string='Overwrite', default=True,
        help="When disabled, the vehicle field is only filled if it is empty.")
    field_available = fields.Boolean(compute='_compute_field_available',
                                     string='Available')
    field_type = fields.Char(compute='_compute_field_available',
                             string='Type')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_field_key', 'unique(field_key)',
         'Each OCR field can only be mapped once.'),
    ]

    @api.depends('field_name')
    def _compute_field_available(self):
        vehicle_fields = self.env['fleet.vehicle']._fields \
            if 'fleet.vehicle' in self.env else {}
        for mapping in self:
            field = vehicle_fields.get(mapping.field_name)
            mapping.field_available = bool(field)
            mapping.field_type = field.type if field else False

    @api.constrains('field_name')
    def _check_field_name(self):
        for mapping in self:
            if mapping.field_name and \
                    mapping.field_name not in self.env['fleet.vehicle']._fields:
                # A warning, not a hard error: the target field may belong to a
                # module that is not installed yet on this database.
                _logger.warning(
                    "Mulkiya mapping: fleet.vehicle has no field '%s', "
                    "the mapping will be skipped.", mapping.field_name)

    @api.depends('field_key', 'field_name')
    def _compute_display_name(self):
        labels = dict(FIELD_KEY_SELECTION)
        for mapping in self:
            mapping.display_name = '%s → %s' % (
                labels.get(mapping.field_key, ''), mapping.field_name or '')

    @api.model
    def get_active_mappings(self):
        """Return only the mappings whose target field really exists."""
        vehicle_fields = self.env['fleet.vehicle']._fields
        return self.sudo().search([]).filtered(
            lambda m: m.field_name in vehicle_fields)

    def _check_write_access(self):
        if not self.env.user.has_group('odex_mulkiya_scan.group_mulkiya_admin'):
            raise ValidationError(_(
                "Only a Mulkiya Scan Administrator can change the Fleet "
                "field mapping."))
