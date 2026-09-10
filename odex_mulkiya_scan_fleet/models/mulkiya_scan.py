# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.odex_mulkiya_scan.services import constants

_logger = logging.getLogger(__name__)


class MulkiyaScan(models.Model):
    _inherit = 'odex.mulkiya.scan'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', copy=False, index=True,
        ondelete='set null',
        help="Vehicle this scan was launched from, or applied to.")
    apply_preview = fields.Text(string='Changes To Apply',
                                compute='_compute_apply_preview')
    can_apply_to_vehicle = fields.Boolean(compute='_compute_can_apply_to_vehicle')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('vehicle_id', 'state')
    def _compute_can_apply_to_vehicle(self):
        for scan in self:
            scan.can_apply_to_vehicle = bool(scan.vehicle_id) and scan.state in (
                constants.STATE_EXTRACTED, constants.STATE_VERIFIED)

    @api.depends('vehicle_id', 'state', 'matched_data',
                 *[column for column in constants.FIELD_TO_COLUMN.values()])
    def _compute_apply_preview(self):
        for scan in self:
            if not scan.vehicle_id or scan.state in (
                    constants.STATE_DRAFT, constants.STATE_UPLOADED,
                    constants.STATE_PROCESSING):
                scan.apply_preview = False
                continue
            values, skipped = scan._prepare_vehicle_values(scan.vehicle_id)
            lines = []
            for field_name, value in values.items():
                field = scan.vehicle_id._fields[field_name]
                current = scan.vehicle_id[field_name]
                if field.type == 'many2one':
                    current = current.display_name if current else _('empty')
                    new = self.env[field.comodel_name].browse(value).display_name
                else:
                    current = current or _('empty')
                    new = value
                lines.append('%s: %s → %s' % (field.string, current, new))
            for reason in skipped:
                lines.append('%s' % reason)
            scan.apply_preview = '\n'.join(lines) or _(
                "Nothing to update: the vehicle already holds these values.")

    # ------------------------------------------------------------------
    # Duplicate detection extended to real vehicles (section 24)
    # ------------------------------------------------------------------
    def _duplicate_check_targets(self):
        targets = super()._duplicate_check_targets()
        if 'fleet.vehicle' in self.env:
            targets.append(('fleet.vehicle', 'vin_sn', _("Vehicle")))
        return targets

    def _build_duplicate_warning(self):
        """Ignore the vehicle the scan is being applied to."""
        self.ensure_one()
        warning = super()._build_duplicate_warning()
        if not warning or not self.vehicle_id:
            return warning
        # The vehicle we are updating is not a duplicate of itself.
        others = self.env['fleet.vehicle'].sudo().search([
            ('vin_sn', '=', self.vin_sn),
            ('id', '!=', self.vehicle_id.id),
        ], limit=1)
        other_scans = self.search_count([
            ('vin_sn', '=', self.vin_sn), ('id', '!=', self.id or 0)])
        return warning if (others or other_scans) else False

    def action_open_duplicates(self):
        self.ensure_one()
        vehicles = self.env['fleet.vehicle'].search([
            ('vin_sn', '=', self.vin_sn),
            ('id', '!=', self.vehicle_id.id or 0),
        ])
        if not vehicles:
            return super().action_open_duplicates()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicles With This Chassis Number'),
            'res_model': 'fleet.vehicle',
            'view_mode': 'list,form',
            'domain': [('id', 'in', vehicles.ids)],
        }

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def action_apply(self):
        """Route to the Fleet application when the scan targets a vehicle."""
        self.ensure_one()
        if self.vehicle_id:
            return self.action_apply_to_vehicle()
        return super().action_apply()

    def action_apply_to_vehicle(self):
        """Write the verified information onto the linked vehicle."""
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("This scan is not linked to a vehicle."))
        if self.state in (constants.STATE_DRAFT, constants.STATE_UPLOADED,
                          constants.STATE_PROCESSING, constants.STATE_FAILED):
            raise UserError(_(
                "Please scan the Mulkiya and verify the extracted information "
                "before applying it to the vehicle."))
        missing = self._missing_required_fields()
        if missing:
            raise UserError(_(
                "The following information is still missing:\n\n%s",
                '\n'.join('- %s' % label for label in missing)))

        vehicle = self.vehicle_id
        values, skipped = self._prepare_vehicle_values(vehicle)
        if values:
            vehicle.write(values)
        self.copy_documents_to(vehicle, prefix=_('Mulkiya'))

        if self.state == constants.STATE_EXTRACTED:
            # Applying is an explicit confirmation of the extracted values.
            self.action_confirm()
        self.mark_applied('%s,%s' % (vehicle._name, vehicle.id))

        body = _("Vehicle information updated from Mulkiya scan %s.", self.name)
        if values:
            body += '<ul>' + ''.join(
                '<li>%s</li>' % vehicle._fields[name].string for name in values
            ) + '</ul>'
        vehicle.message_post(body=body)
        if skipped:
            self.message_post(body=_(
                "Some values were not applied:<br/>%s",
                '<br/>'.join(skipped)))

        return {
            'type': 'ir.actions.act_window_close',
        }

    # ------------------------------------------------------------------
    def _prepare_vehicle_values(self, vehicle):
        """Build the write values for ``vehicle``.

        :return: tuple ``(values, skipped_messages)``
        """
        self.ensure_one()
        values = {}
        skipped = []
        mappings = self.env['odex.mulkiya.fleet.mapping'].get_active_mappings()
        vehicle_fields = vehicle._fields

        for mapping in mappings:
            field = vehicle_fields.get(mapping.field_name)
            if not field:
                continue
            column = constants.FIELD_TO_COLUMN[mapping.field_key]
            raw_value = self[column]
            label = constants.FIELD_LABELS[mapping.field_key]
            if raw_value in (None, '', False) or \
                    (field.type == 'integer' and not raw_value):
                continue
            if not mapping.overwrite and vehicle[mapping.field_name]:
                continue

            if field.type == 'many2one':
                target = False
                if mapping.use_matched_record:
                    record = self.get_matched_record(mapping.field_key)
                    if record and record._name == field.comodel_name:
                        target = record.id
                if not target:
                    target = self._find_relational_target(field, raw_value)
                if not target:
                    skipped.append(_(
                        "%(label)s: '%(value)s' has no matching record in "
                        "%(model)s, please create it first.",
                        label=label, value=raw_value,
                        model=field.comodel_name))
                    continue
                if vehicle[mapping.field_name].id != target:
                    values[mapping.field_name] = target
            elif field.type == 'selection':
                target = self._match_selection(vehicle, mapping.field_name,
                                               raw_value)
                if not target:
                    skipped.append(_(
                        "%(label)s: '%(value)s' is not an available option on "
                        "the vehicle.", label=label, value=raw_value))
                    continue
                if vehicle[mapping.field_name] != target:
                    values[mapping.field_name] = target
            elif field.type == 'integer':
                if vehicle[mapping.field_name] != int(raw_value):
                    values[mapping.field_name] = int(raw_value)
            elif field.type in ('char', 'text'):
                if (vehicle[mapping.field_name] or '') != raw_value:
                    values[mapping.field_name] = raw_value
            else:
                skipped.append(_(
                    "%(label)s: field type '%(type)s' is not supported.",
                    label=label, type=field.type))
        return values, skipped

    def _find_relational_target(self, field, value):
        """Last resort lookup when the scan carries no matched record."""
        comodel = self.env[field.comodel_name].sudo()
        if 'name' not in comodel._fields:
            return False
        record = comodel.search([('name', '=ilike', value)], limit=1)
        return record.id if record else False

    def _match_selection(self, vehicle, field_name, value):
        """Match a text value against the selection keys and labels."""
        selection = vehicle._fields[field_name]._description_selection(self.env)
        normalized = (value or '').strip().lower()
        for key, label in selection:
            if normalized in (str(key).lower(), str(label).lower()):
                return key
        return False

    # ------------------------------------------------------------------
    # Client API - fills a vehicle form that may not be saved yet
    # ------------------------------------------------------------------
    @api.model
    def get_field_options(self):
        """Add the Fleet selection fields to the dialog dropdowns."""
        options = super().get_field_options()
        field = self.env['fleet.vehicle']._fields.get('fuel_type')
        if field and field.type == 'selection':
            options[constants.FIELD_FUEL_TYPE] = [
                {'id': False, 'name': label}
                for _key, label in field._description_selection(self.env)
            ]
        return options

    def apply_to_form(self, values=None, vehicle_id=False, selected=None):
        """Confirm the scan and return values ready to push into a form.

        This is what makes the scanner usable while creating a vehicle: the
        record does not exist yet, so nothing is written to Fleet here. The
        values travel back to the browser and land in the open form.
        """
        self.ensure_one()
        if values or selected:
            self.update_values(values or {}, selected=selected)
        missing = self._missing_required_fields()
        if missing:
            return {
                'success': False,
                'error': _("The following information is still missing:\n\n%s",
                           '\n'.join('- %s' % label for label in missing)),
            }

        vehicle = self.env['fleet.vehicle'].browse(vehicle_id) \
            if vehicle_id else self.env['fleet.vehicle']
        if vehicle and vehicle.exists():
            self.vehicle_id = vehicle
        elif vehicle_id:
            vehicle = self.env['fleet.vehicle']

        form_values, skipped = self._prepare_form_values(vehicle)
        if self.state == constants.STATE_EXTRACTED:
            self.action_confirm()
        if vehicle:
            self.copy_documents_to(vehicle, prefix=_('Mulkiya'))
            self.mark_applied('%s,%s' % (vehicle._name, vehicle.id))
        return {
            'success': True,
            'scan_id': self.id,
            'form_values': form_values,
            'skipped': skipped,
        }

    def link_vehicle(self, vehicle_id):
        """Attach the scan and its documents to a vehicle saved after scanning."""
        self.ensure_one()
        vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
        if not vehicle.exists():
            return False
        self.vehicle_id = vehicle
        self.copy_documents_to(vehicle, prefix=_('Mulkiya'))
        if self.state == constants.STATE_VERIFIED:
            self.mark_applied('%s,%s' % (vehicle._name, vehicle.id))
        return True

    def _prepare_form_values(self, vehicle=None):
        """Mapping-driven values in the shape the web client expects.

        Relational fields come back as ``{'id':.., 'display_name':..}`` so the
        form can show them without a round trip.
        """
        self.ensure_one()
        Vehicle = self.env['fleet.vehicle']
        vehicle_fields = Vehicle._fields
        form_values = {}
        skipped = []

        for mapping in self.env['odex.mulkiya.fleet.mapping'].get_active_mappings():
            field = vehicle_fields.get(mapping.field_name)
            if not field:
                continue
            column = constants.FIELD_TO_COLUMN[mapping.field_key]
            raw_value = self[column]
            label = constants.FIELD_LABELS[mapping.field_key]
            if raw_value in (None, '', False):
                continue
            if not mapping.overwrite and vehicle and vehicle.exists() \
                    and vehicle[mapping.field_name]:
                continue

            if field.type == 'many2one':
                record = None
                if mapping.use_matched_record:
                    matched = self.get_matched_record(mapping.field_key)
                    if matched and matched._name == field.comodel_name:
                        record = matched
                if not record:
                    record_id = self._find_relational_target(field, raw_value)
                    record = self.env[field.comodel_name].browse(record_id) \
                        if record_id else None
                if not record:
                    skipped.append(_(
                        "%(label)s: '%(value)s' has no matching record in "
                        "%(model)s, please create it first.",
                        label=label, value=raw_value, model=field.comodel_name))
                    continue
                form_values[mapping.field_name] = {
                    'id': record.id,
                    'display_name': record.display_name,
                }
            elif field.type == 'selection':
                target = self._match_selection_generic(field, raw_value)
                if not target:
                    skipped.append(_(
                        "%(label)s: '%(value)s' is not an available option on "
                        "the vehicle.", label=label, value=raw_value))
                    continue
                form_values[mapping.field_name] = target
            elif field.type == 'integer':
                form_values[mapping.field_name] = int(raw_value or 0)
            elif field.type in ('char', 'text'):
                form_values[mapping.field_name] = raw_value
            else:
                skipped.append(_(
                    "%(label)s: field type '%(type)s' is not supported.",
                    label=label, type=field.type))
        return form_values, skipped

    def _match_selection_generic(self, field, value):
        selection = field._description_selection(self.env)
        normalized = (value or '').strip().lower()
        for key, label in selection:
            if normalized in (str(key).lower(), str(label).lower()):
                return key
        return False

    # ------------------------------------------------------------------
    def get_structured_result(self):
        result = super().get_structured_result()
        result['vehicle_id'] = self.vehicle_id.id or False
        return result
