# -*- coding: utf-8 -*-
import json
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import constants
from ..services.ocr_service import MulkiyaOcrService

_logger = logging.getLogger(__name__)


class MulkiyaScan(models.Model):
    """One scan of one Mulkiya, from upload to verified structured data.

    This model is the public face of the application. Other Odex applications
    consume it through :meth:`get_vehicle_data` and :meth:`get_structured_result`
    and must never read the private columns directly.
    """

    _name = 'odex.mulkiya.scan'
    _description = 'Mulkiya Scan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # ------------------------------------------------------------------
    # Identification and workflow
    # ------------------------------------------------------------------
    name = fields.Char(string='Scan Number', default='/', copy=False,
                       readonly=True, index=True)
    state = fields.Selection(constants.SCAN_STATES, string='Status',
                             default=constants.STATE_DRAFT, required=True,
                             copy=False, tracking=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    source_reference = fields.Char(
        string='Source', copy=False, readonly=True,
        help="Application that created this scan, for example "
             "fleet.vehicle,42 when it was launched from a vehicle.")

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    front_image = fields.Image(string='Front Side', attachment=True, copy=False,
                               max_width=2560, max_height=2560)
    back_image = fields.Image(string='Back Side', attachment=True, copy=False,
                              max_width=2560, max_height=2560)
    front_filename = fields.Char(copy=False)
    back_filename = fields.Char(copy=False)
    has_both_images = fields.Boolean(compute='_compute_has_both_images')

    # ------------------------------------------------------------------
    # Extracted vehicle information (canonical keys, see services.constants)
    # ------------------------------------------------------------------
    engine_no = fields.Char(string='Engine Number', tracking=True)
    vin_sn = fields.Char(string='Chassis Number / VIN', tracking=True, index=True)
    license_plate = fields.Char(string='Plate Number', tracking=True, index=True)
    plate_code = fields.Char(string='Plate Code', tracking=True)
    registration_emirate = fields.Char(string='Registration Emirate', tracking=True)
    make = fields.Char(string='Make', tracking=True)
    vehicle_model = fields.Char(string='Model', tracking=True)
    model_year = fields.Char(string='Model Year', tracking=True)
    color = fields.Char(string='Colour', tracking=True)
    fuel_type = fields.Char(string='Fuel Type', tracking=True)
    cylinder_count = fields.Integer(string='Number of Cylinders', tracking=True)

    # ------------------------------------------------------------------
    # Per field confidence (section 19)
    # ------------------------------------------------------------------
    engine_no_conf = fields.Integer(string='Engine Number Confidence', readonly=True)
    vin_sn_conf = fields.Integer(string='VIN Confidence', readonly=True)
    license_plate_conf = fields.Integer(string='Plate Confidence', readonly=True)
    plate_code_conf = fields.Integer(string='Plate Code Confidence', readonly=True)
    registration_emirate_conf = fields.Integer(string='Emirate Confidence',
                                               readonly=True)
    make_conf = fields.Integer(string='Make Confidence', readonly=True)
    vehicle_model_conf = fields.Integer(string='Model Confidence', readonly=True)
    model_year_conf = fields.Integer(string='Year Confidence', readonly=True)
    color_conf = fields.Integer(string='Colour Confidence', readonly=True)
    fuel_type_conf = fields.Integer(string='Fuel Type Confidence', readonly=True)
    cylinder_count_conf = fields.Integer(string='Cylinders Confidence', readonly=True)

    ocr_confidence = fields.Integer(string='Overall Confidence', readonly=True,
                                    aggregator='avg')
    confidence_threshold = fields.Integer(compute='_compute_confidence_threshold',
                                          string='Threshold')
    low_confidence_count = fields.Integer(compute='_compute_low_confidence_count',
                                          string='Fields To Verify')
    show_confidence = fields.Boolean(compute='_compute_show_confidence')

    # ------------------------------------------------------------------
    # OCR technical information
    # ------------------------------------------------------------------
    ocr_status = fields.Selection(
        [('pending', 'Pending'), ('done', 'Done'), ('error', 'Error')],
        string='OCR Status', default='pending', copy=False, readonly=True)
    ocr_provider = fields.Char(string='OCR Provider', copy=False, readonly=True)
    ocr_date = fields.Datetime(string='OCR Processed On', copy=False, readonly=True)
    ocr_duration = fields.Float(string='OCR Duration (s)', copy=False, readonly=True)
    ocr_error = fields.Text(string='OCR Error', copy=False, readonly=True)
    ocr_simulated = fields.Boolean(string='Simulated Result', copy=False,
                                   readonly=True)
    ocr_raw_response = fields.Text(string='Raw OCR Response', copy=False,
                                   readonly=True)
    matched_data = fields.Json(string='Matched Master Data', copy=False,
                               readonly=True)
    matched_summary = fields.Text(string='Matching Summary',
                                  compute='_compute_matched_summary')

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------
    vin_warning = fields.Text(string='VIN Warning', copy=False, readonly=True)
    duplicate_warning = fields.Text(string='Duplicate Warning',
                                    compute='_compute_duplicate_warning')
    unmatched_warning = fields.Text(string='Unmatched Fields', copy=False,
                                    readonly=True)
    quality_warning = fields.Text(string='Image Quality Warning', copy=False,
                                  readonly=True)

    # ------------------------------------------------------------------
    # Audit trail (section 37)
    # ------------------------------------------------------------------
    verified_uid = fields.Many2one('res.users', string='Verified By',
                                   copy=False, readonly=True)
    verified_date = fields.Datetime(string='Verified On', copy=False, readonly=True)
    applied_uid = fields.Many2one('res.users', string='Applied By',
                                  copy=False, readonly=True)
    applied_date = fields.Datetime(string='Applied On', copy=False, readonly=True)
    applied_reference = fields.Char(string='Applied To', copy=False, readonly=True)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends('front_image', 'back_image')
    def _compute_has_both_images(self):
        for scan in self:
            scan.has_both_images = bool(scan.front_image and scan.back_image)

    def _compute_confidence_threshold(self):
        threshold = MulkiyaOcrService(self.env).get_threshold()
        for scan in self:
            scan.confidence_threshold = threshold

    @api.depends('ocr_confidence', 'state')
    def _compute_show_confidence(self):
        for scan in self:
            scan.show_confidence = scan.state in (
                constants.STATE_EXTRACTED, constants.STATE_VERIFIED,
                constants.STATE_APPLIED)

    @api.depends(lambda self: [
        col + constants.CONFIDENCE_SUFFIX
        for col in constants.FIELD_TO_COLUMN.values()
    ] + list(constants.FIELD_TO_COLUMN.values()) + ['state'])
    def _compute_low_confidence_count(self):
        threshold = MulkiyaOcrService(self.env).get_threshold()
        for scan in self:
            count = 0
            if scan.state in (constants.STATE_EXTRACTED, constants.STATE_VERIFIED):
                for column in constants.FIELD_TO_COLUMN.values():
                    if not scan[column]:
                        continue
                    confidence = scan[column + constants.CONFIDENCE_SUFFIX]
                    if confidence and confidence < threshold:
                        count += 1
            scan.low_confidence_count = count

    @api.depends('matched_data')
    def _compute_matched_summary(self):
        for scan in self:
            data = scan.matched_data or {}
            if not data:
                scan.matched_summary = False
                continue
            lines = []
            for key in constants.MULKIYA_FIELDS:
                match = data.get(key) or {}
                if not match.get('model'):
                    continue
                label = constants.FIELD_LABELS.get(key, key)
                if match.get('matched'):
                    lines.append('%s: %s (%s #%s)' % (
                        label, match.get('record_name') or match.get('value'),
                        match.get('model'), match.get('record_id')))
                elif match.get('value'):
                    lines.append('%s: %s — no match in %s' % (
                        label, match.get('value'), match.get('model')))
            scan.matched_summary = '\n'.join(lines) or False

    @api.depends('vin_sn', 'state')
    def _compute_duplicate_warning(self):
        for scan in self:
            scan.duplicate_warning = scan._build_duplicate_warning()

    # ==================================================================
    # ORM
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.mulkiya.scan') or '/'
            self._sync_state_on_images(vals=vals)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if 'front_image' in vals or 'back_image' in vals:
            self._sync_state_on_images()
        return result

    def _sync_state_on_images(self, vals=None):
        """Move draft <-> uploaded automatically when the images change."""
        if vals is not None:
            # create(): work on the values dict, no record exists yet.
            if vals.get('state') in (None, constants.STATE_DRAFT,
                                     constants.STATE_UPLOADED):
                vals['state'] = constants.STATE_UPLOADED \
                    if (vals.get('front_image') and vals.get('back_image')) \
                    else constants.STATE_DRAFT
            return vals
        for scan in self:
            if scan.state not in (constants.STATE_DRAFT, constants.STATE_UPLOADED):
                continue
            target = constants.STATE_UPLOADED if scan.has_both_images \
                else constants.STATE_DRAFT
            if scan.state != target:
                super(MulkiyaScan, scan).write({'state': target})
        return True

    @api.depends('name', 'vin_sn', 'license_plate')
    def _compute_display_name(self):
        for scan in self:
            parts = [scan.name or _('New')]
            if scan.license_plate:
                parts.append(scan.license_plate)
            elif scan.vin_sn:
                parts.append(scan.vin_sn)
            scan.display_name = ' - '.join(parts)

    def unlink(self):
        blocked = self.filtered(lambda s: s.state == constants.STATE_APPLIED)
        if blocked and not self.env.user.has_group(
                'odex_mulkiya_scan.group_mulkiya_admin'):
            raise UserError(_(
                "Applied scans are part of the audit trail and cannot be deleted. "
                "You can archive them instead."))
        return super().unlink()

    # ==================================================================
    # Workflow
    # ==================================================================
    def action_scan(self):
        """Run OCR on both sides and fill the extracted information."""
        self.ensure_one()
        if not self.front_image:
            raise UserError(_("Please upload the front side of the Mulkiya."))
        if not self.back_image:
            raise UserError(_("Please upload the back side of the Mulkiya."))
        self._lock_for_processing()

        self.write({
            'state': constants.STATE_PROCESSING,
            'ocr_status': 'pending',
            'ocr_error': False,
        })

        service = MulkiyaOcrService(self.env)
        try:
            result = service.scan(self.front_image, self.back_image)
        except UserError as exc:
            # The failure is part of the audit trail, so it must survive the
            # request: register it and report through a notification instead of
            # raising, which would roll the transaction back.
            self._register_failure(str(exc))
            return self._notify(_("Scan failed"), str(exc), 'danger')
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Mulkiya scan %s crashed", self.name)
            self._register_failure(str(exc))
            return self._notify(
                _("Scan failed"),
                _("Unable to process the Mulkiya.\n\n"
                  "Please verify the image quality and try again."), 'danger')

        self._apply_ocr_result(result)
        return self._reload_action()

    def _lock_for_processing(self):
        """Prevent a double submission of the same scan (section 14)."""
        self.ensure_one()
        if not self.id:
            return
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM odex_mulkiya_scan WHERE id = %s "
                    "FOR UPDATE NOWAIT", (self.id,))
        except Exception as exc:
            raise UserError(_(
                "This Mulkiya is already being processed. "
                "Please wait for the current scan to finish.")) from exc

    def _notify(self, title, message, notification_type='warning'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': notification_type == 'danger',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_rescan(self):
        """Clear the previous result and run OCR again."""
        self.ensure_one()
        self._clear_result()
        return self.action_scan()

    def action_confirm(self):
        """User verified the extracted information (section 29)."""
        for scan in self:
            if scan.state not in (constants.STATE_EXTRACTED,
                                  constants.STATE_FAILED):
                raise UserError(_(
                    "Only extracted scans can be confirmed."))
            missing = scan._missing_required_fields()
            if missing:
                raise UserError(_(
                    "The following information is still missing:\n\n%s",
                    '\n'.join('- %s' % label for label in missing)))
            scan.write({
                'state': constants.STATE_VERIFIED,
                'verified_uid': self.env.user.id,
                'verified_date': fields.Datetime.now(),
            })
            scan.message_post(body=_("Extracted information verified."))
        return True

    def action_reset_to_draft(self):
        for scan in self:
            scan.write({
                'state': constants.STATE_UPLOADED if scan.has_both_images
                         else constants.STATE_DRAFT,
                'verified_uid': False,
                'verified_date': False,
            })
        return True

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apply(self):
        """Hand the verified result to the consumer application.

        The core application has no idea what "applying" means: integration
        modules (``odex_mulkiya_scan_fleet`` and friends) override this. When no
        consumer is installed the scan simply stays verified.
        """
        self.ensure_one()
        raise UserError(_(
            "No target application is installed to receive this scan.\n\n"
            "The verified data is available to any Odex application through "
            "the scan result interface."))

    def mark_applied(self, reference=None):
        """Called by an integration module once the data has been applied."""
        self.write({
            'state': constants.STATE_APPLIED,
            'applied_uid': self.env.user.id,
            'applied_date': fields.Datetime.now(),
            'applied_reference': reference or False,
        })
        if reference:
            self.message_post(body=_("Applied to %s.", reference))
        return True

    # ==================================================================
    # Result handling
    # ==================================================================
    def _apply_ocr_result(self, result):
        self.ensure_one()
        values = {
            'state': constants.STATE_EXTRACTED,
            'ocr_status': 'done',
            'ocr_provider': result.get('provider'),
            'ocr_simulated': bool(result.get('simulated')),
            'ocr_date': fields.Datetime.now(),
            'ocr_duration': result.get('duration') or 0.0,
            'ocr_confidence': result.get('confidence') or 0,
            'ocr_error': False,
            'matched_data': result.get('matches') or {},
        }
        try:
            values['ocr_raw_response'] = json.dumps(
                result.get('raw') or {}, ensure_ascii=False, indent=2)[:200000]
        except (TypeError, ValueError):  # pragma: no cover - defensive
            values['ocr_raw_response'] = str(result.get('raw'))[:200000]

        for key, column in constants.FIELD_TO_COLUMN.items():
            entry = (result.get('fields') or {}).get(key) or {}
            value = entry.get('value')
            if key in constants.INTEGER_FIELDS:
                values[column] = int(value or 0)
            else:
                values[column] = value or False
            values[column + constants.CONFIDENCE_SUFFIX] = entry.get('confidence') or 0

        warnings = result.get('warnings') or {}
        values['quality_warning'] = warnings.get('quality') or False
        values['vin_warning'] = '\n'.join(warnings.get('vin') or []) or False
        unmatched = warnings.get('unmatched') or []
        values['unmatched_warning'] = _(
            "Some information could not be matched with system master data. "
            "Please review: %s", ', '.join(unmatched)) if unmatched else False

        self.write(values)
        self.message_post(body=_(
            "Mulkiya processed by %(provider)s in %(duration)ss. "
            "Overall confidence: %(confidence)s%%.",
            provider=result.get('provider'),
            duration=result.get('duration'),
            confidence=result.get('confidence')))
        return True

    def _register_failure(self, message):
        self.sudo().write({
            'state': constants.STATE_FAILED,
            'ocr_status': 'error',
            'ocr_error': message,
            'ocr_date': fields.Datetime.now(),
        })
        self.message_post(body=_("OCR failed: %s", message))

    def _clear_result(self):
        values = {
            'ocr_status': 'pending',
            'ocr_error': False,
            'ocr_confidence': 0,
            'matched_data': {},
            'vin_warning': False,
            'unmatched_warning': False,
            'verified_uid': False,
            'verified_date': False,
        }
        for column in constants.FIELD_TO_COLUMN.values():
            values[column] = 0 if column == 'cylinder_count' else False
            values[column + constants.CONFIDENCE_SUFFIX] = 0
        values['state'] = constants.STATE_UPLOADED if self.has_both_images \
            else constants.STATE_DRAFT
        return self.write(values)

    def _missing_required_fields(self):
        self.ensure_one()
        required = [constants.FIELD_VIN, constants.FIELD_PLATE]
        missing = []
        for key in required:
            if not self[constants.FIELD_TO_COLUMN[key]]:
                missing.append(constants.FIELD_LABELS[key])
        return missing

    def _reload_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    # ==================================================================
    # Duplicate detection (section 24)
    # ==================================================================
    def _duplicate_check_targets(self):
        """Models to check for an existing VIN.

        Integration modules extend this. The core only knows about other scans.
        """
        return [(self._name, 'vin_sn', _("Mulkiya Scan"))]

    def _build_duplicate_warning(self):
        self.ensure_one()
        if not self.vin_sn:
            return False
        messages = []
        for model_name, field_name, label in self._duplicate_check_targets():
            if model_name not in self.env:
                continue
            model = self.env[model_name].sudo()
            if field_name not in model._fields:
                continue
            domain = [(field_name, '=', self.vin_sn)]
            if model_name == self._name:
                domain.append(('id', '!=', self.id or 0))
            records = model.search(domain, limit=3)
            for record in records:
                messages.append('%s: %s' % (label, record.display_name))
        if not messages:
            return False
        return _(
            "This chassis number already exists in the system:\n\n%s\n\n"
            "Please verify before applying.", '\n'.join(messages))

    def action_open_duplicates(self):
        """Open the records that already use this VIN."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Existing Scans With This VIN'),
            'res_model': self._name,
            'view_mode': 'list,form',
            'domain': [('vin_sn', '=', self.vin_sn), ('id', '!=', self.id)],
        }

    # ==================================================================
    # Public result interface (sections 22 and 41)
    # ==================================================================
    def get_vehicle_data(self):
        """Flat, canonical vehicle data.

        This is the contract every other Odex application should use.
        """
        self.ensure_one()
        data = {}
        for key, column in constants.FIELD_TO_COLUMN.items():
            value = self[column]
            if key in constants.INTEGER_FIELDS:
                data[key] = int(value or 0)
            else:
                data[key] = value or ''
        return data

    def get_structured_result(self):
        """Canonical data enriched with confidence and matched record ids."""
        self.ensure_one()
        matches = self.matched_data or {}
        fields_payload = {}
        for key, column in constants.FIELD_TO_COLUMN.items():
            value = self[column]
            match = matches.get(key) or {}
            fields_payload[key] = {
                'value': int(value or 0) if key in constants.INTEGER_FIELDS
                         else (value or ''),
                'confidence': self[column + constants.CONFIDENCE_SUFFIX] or 0,
                'matched': bool(match.get('matched')),
                'model': match.get('model') or False,
                'record_id': match.get('record_id') or False,
                'record_name': match.get('record_name') or False,
            }
        return {
            'success': self.state in (constants.STATE_VERIFIED,
                                      constants.STATE_APPLIED,
                                      constants.STATE_EXTRACTED),
            'scan_id': self.id,
            'scan_number': self.name,
            'status': self.state,
            'confidence': self.ocr_confidence,
            'confidence_threshold': self.confidence_threshold,
            'provider': self.ocr_provider or False,
            'warnings': {
                'vin': self.vin_warning or False,
                'duplicate': self.duplicate_warning or False,
                'unmatched': self.unmatched_warning or False,
                'quality': self.quality_warning or False,
            },
            'vehicle': self.get_vehicle_data(),
            'fields': fields_payload,
        }

    def get_matched_record(self, field_key):
        """Return the matched recordset for a canonical field, if any."""
        self.ensure_one()
        match = (self.matched_data or {}).get(field_key) or {}
        model_name = match.get('model')
        record_id = match.get('record_id')
        if not model_name or not record_id or model_name not in self.env:
            return None
        record = self.env[model_name].browse(record_id)
        return record if record.exists() else None

    # ==================================================================
    # Client API - used by the in-form scanner dialog
    # ==================================================================
    @api.model
    def scan_from_images(self, front_image, back_image, source_reference=False,
                         vehicle_id=False):
        """Create a scan from two base64 images, run OCR and return the result.

        Used by the scanner dialog, which may run on a record that has not been
        saved yet: nothing is written outside the scan itself.
        """
        values = {
            'front_image': front_image,
            'back_image': back_image,
            'source_reference': source_reference or False,
        }
        if vehicle_id and 'vehicle_id' in self._fields:
            values['vehicle_id'] = vehicle_id
        scan = self.create(values)
        service = MulkiyaOcrService(self.env)
        try:
            result = service.scan(scan.front_image, scan.back_image)
        except UserError as exc:
            scan._register_failure(str(exc))
            return {
                'success': False,
                'scan_id': scan.id,
                'scan_number': scan.name,
                'error': str(exc),
            }
        scan._apply_ocr_result(result)
        return scan._client_payload()

    @api.model
    def get_field_options(self):
        """Master data choices offered by the scanner dialog.

        Built from the matching rules, so the dropdowns always reflect what
        actually exists in this database. Fields without a rule stay free text.
        """
        options = {}
        rules = self.env['odex.mulkiya.match.rule'].sudo().search([])
        for rule in rules:
            if not rule.model_name or rule.model_name not in self.env:
                continue
            model = self.env[rule.model_name].sudo()
            field_name = rule.search_field or 'name'
            if field_name not in model._fields:
                continue
            try:
                records = model.search([], limit=500)
            except Exception:  # pragma: no cover - defensive
                continue
            entries = []
            for record in records:
                name = record[field_name] or record.display_name
                if not name:
                    continue
                entry = {'id': record.id, 'name': name}
                if rule.parent_relation_field and \
                        rule.parent_relation_field in model._fields:
                    parent = record[rule.parent_relation_field]
                    entry['parent_id'] = parent.id if parent else False
                    entry['parent_key'] = rule.parent_field_key or False
                entries.append(entry)
            entries.sort(key=lambda item: (item['name'] or '').lower())
            options.setdefault(rule.field_key, []).extend(entries)

        current_year = date.today().year + 1
        options.setdefault(constants.FIELD_MODEL_YEAR, [
            {'id': False, 'name': str(year)}
            for year in range(current_year, current_year - 46, -1)
        ])
        return options

    def update_values(self, values, selected=None):
        """Write user corrections and re-run the master data matching.

        ``selected`` maps a field key to the master record the user explicitly
        picked in a dropdown; that choice always wins over automatic matching.
        """
        self.ensure_one()
        write_values = {}
        for key, value in (values or {}).items():
            column = constants.FIELD_TO_COLUMN.get(key)
            if not column:
                continue
            if key in constants.INTEGER_FIELDS:
                try:
                    write_values[column] = int(value or 0)
                except (TypeError, ValueError):
                    write_values[column] = 0
            else:
                write_values[column] = value or False
        if write_values:
            self.write(write_values)
        if write_values or selected:
            self._rematch()
            self._apply_explicit_selection(selected)
        return self._client_payload()

    def _apply_explicit_selection(self, selected):
        """Pin the master records the user picked by hand."""
        self.ensure_one()
        if not selected:
            return
        matches = dict(self.matched_data or {})
        rules = self.env['odex.mulkiya.match.rule'].sudo().search([])
        rule_by_key = {rule.field_key: rule for rule in rules}
        for key, record_id in selected.items():
            rule = rule_by_key.get(key)
            if not record_id or not rule or rule.model_name not in self.env:
                continue
            record = self.env[rule.model_name].sudo().browse(int(record_id))
            if not record.exists():
                continue
            entry = dict(matches.get(key) or {})
            entry.update({
                'value': self[constants.FIELD_TO_COLUMN[key]],
                'matched': True,
                'model': rule.model_name,
                'record_id': record.id,
                'record_name': record[rule.search_field or 'name'] or
                               record.display_name,
            })
            matches[key] = entry
        self.write({'matched_data': matches})

    def _rematch(self):
        """Recompute matching and warnings from the current stored values."""
        self.ensure_one()
        service = MulkiyaOcrService(self.env)
        payload = {}
        for key, column in constants.FIELD_TO_COLUMN.items():
            payload[key] = {
                'value': self[column],
                'confidence': self[column + constants.CONFIDENCE_SUFFIX],
            }
        matches = service.matcher.match_payload(payload)
        warnings = service.build_warnings(payload, matches,
                                          self.confidence_threshold)
        unmatched = warnings.get('unmatched') or []
        self.write({
            'matched_data': matches,
            'vin_warning': '\n'.join(warnings.get('vin') or []) or False,
            'unmatched_warning': _(
                "Some information could not be matched with system master data. "
                "Please review: %s", ', '.join(unmatched)) if unmatched else False,
        })
        return matches

    def _client_payload(self):
        """Everything the scanner dialog needs to render the result."""
        self.ensure_one()
        matches = self.matched_data or {}
        fields_payload = []
        for key in constants.MULKIYA_FIELDS:
            column = constants.FIELD_TO_COLUMN[key]
            match = matches.get(key) or {}
            value = self[column]
            fields_payload.append({
                'key': key,
                'label': constants.FIELD_LABELS[key],
                'value': '' if value in (False, None) else str(value),
                'confidence': self[column + constants.CONFIDENCE_SUFFIX] or 0,
                'matched': bool(match.get('matched')),
                'match_model': match.get('model') or False,
                'match_name': match.get('record_name') or False,
            })
        return {
            'success': True,
            'scan_id': self.id,
            'scan_number': self.name,
            'state': self.state,
            'simulated': self.ocr_simulated,
            'threshold': self.confidence_threshold,
            'confidence': self.ocr_confidence,
            'fields': fields_payload,
            'warnings': {
                'vin': self.vin_warning or False,
                'duplicate': self.duplicate_warning or False,
                'unmatched': self.unmatched_warning or False,
            },
        }

    # ==================================================================
    # Attachments (section 25)
    # ==================================================================
    def get_document_attachments(self):
        """Return ``ir.attachment`` records for both Mulkiya sides."""
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', 'in', ['front_image', 'back_image']),
        ])

    def copy_documents_to(self, record, prefix=None):
        """Duplicate the Mulkiya images as normal attachments on ``record``."""
        self.ensure_one()
        prefix = prefix or _('Mulkiya')
        Attachment = self.env['ir.attachment'].sudo()
        created = Attachment
        for field_name, label in (('front_image', _('Front')),
                                  ('back_image', _('Back'))):
            data = self[field_name]
            if not data:
                continue
            created |= Attachment.create({
                'name': '%s - %s.jpg' % (prefix, label),
                'datas': data,
                'res_model': record._name,
                'res_id': record.id,
                'mimetype': 'image/jpeg',
            })
        return created

    # ==================================================================
    # Dashboard helper (section 33)
    # ==================================================================
    @api.model
    def get_dashboard_data(self):
        domain = []
        counts = {'total': self.search_count(domain)}
        for state, _label in constants.SCAN_STATES:
            counts[state] = self.search_count(domain + [('state', '=', state)])
        counts['mine'] = self.search_count(
            domain + [('create_uid', '=', self.env.uid)])
        recent = self.search_read(
            domain,
            ['name', 'create_date', 'vin_sn', 'license_plate', 'make',
             'vehicle_model', 'registration_emirate', 'state', 'ocr_confidence'],
            limit=8)
        return {
            'counts': counts,
            'recent': recent,
            'states': dict(constants.SCAN_STATES),
            'can_configure': self.env.user.has_group(
                'odex_mulkiya_scan.group_mulkiya_admin'),
        }
