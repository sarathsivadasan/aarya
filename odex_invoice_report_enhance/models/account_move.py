# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Candidate relations / field names used to locate vehicle information.
# The ODEX WMS stores the vehicle on the job card (and/or the sale order).
# We probe defensively so this report module never hard-depends on a schema
# that may differ across installations and stays upgrade-safe.
# ---------------------------------------------------------------------------
_MOVE_VEHICLE_RELATIONS = (
    'vehicle_id', 'fleet_vehicle_id', 'x_vehicle_id',
)
_MOVE_JOBCARD_RELATIONS = (
    'job_card_id', 'jobcard_id', 'x_job_card_id', 'job_card',
)
_JOBCARD_VEHICLE_RELATIONS = (
    'vehicle_id', 'fleet_vehicle_id', 'x_vehicle_id',
)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # -- Document title ----------------------------------------------------
    odex_document_title = fields.Char(
        string='ODEX Document Title',
        compute='_compute_odex_document_title',
        compute_sudo=True,
    )

    # -- Parts / Labour split lines ---------------------------------------
    odex_parts_line_ids = fields.Many2many(
        'account.move.line',
        string='ODEX Parts Lines',
        compute='_compute_odex_section_lines',
        compute_sudo=True,
    )
    odex_labour_line_ids = fields.Many2many(
        'account.move.line',
        string='ODEX Labour Lines',
        compute='_compute_odex_section_lines',
        compute_sudo=True,
    )

    # -- Section totals ----------------------------------------------------
    odex_parts_amount_untaxed = fields.Monetary(
        string='Total Parts (Excl. Tax)',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')
    odex_parts_amount_tax = fields.Monetary(
        string='Parts Taxes',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')
    odex_parts_amount_total = fields.Monetary(
        string='Total Parts (Incl. Tax)',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')
    odex_labour_amount_untaxed = fields.Monetary(
        string='Total Labour (Excl. Tax)',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')
    odex_labour_amount_tax = fields.Monetary(
        string='Labour Taxes',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')
    odex_labour_amount_total = fields.Monetary(
        string='Total Labour (Incl. Tax)',
        compute='_compute_odex_section_totals', compute_sudo=True,
        currency_field='currency_id')

    # -- Vehicle details (display-only, resolved defensively) --------------
    # odex_vehicle_license_plate = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_make = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_model = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_variant = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_year = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_chassis = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_engine = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_fuel_type = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_transmission = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_odometer = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_vehicle_color = fields.Char(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)
    # odex_has_vehicle = fields.Boolean(
    #     compute='_compute_odex_vehicle_info', compute_sudo=True)

    # -- Portal QR code ----------------------------------------------------
    odex_qr_code = fields.Binary(
        string='ODEX Portal QR',
        compute='_compute_odex_qr_code', compute_sudo=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('move_type', 'state')
    def _compute_odex_document_title(self):
        for move in self:
            if move.move_type == 'out_refund':
                title = 'TAX CREDIT NOTE'
            elif move.move_type == 'in_refund':
                title = 'VENDOR CREDIT NOTE'
            elif move.move_type in ('in_invoice',):
                title = 'VENDOR BILL'
            else:  # out_invoice and fallback
                title = ('TAX PROFORMA INVOICE'
                         if move.state != 'posted' else 'TAX INVOICE')
            move.odex_document_title = title

    @api.depends('invoice_line_ids', 'invoice_line_ids.display_type',
                 'invoice_line_ids.odex_line_kind')
    def _compute_odex_section_lines(self):
        for move in self:
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')
            move.odex_parts_line_ids = product_lines.filtered(
                lambda l: l.odex_line_kind == 'parts')
            move.odex_labour_line_ids = product_lines.filtered(
                lambda l: l.odex_line_kind == 'labour')

    @api.depends('odex_parts_line_ids', 'odex_labour_line_ids',
                 'odex_parts_line_ids.price_subtotal',
                 'odex_parts_line_ids.price_total',
                 'odex_labour_line_ids.price_subtotal',
                 'odex_labour_line_ids.price_total')
    def _compute_odex_section_totals(self):
        for move in self:
            parts = move.odex_parts_line_ids
            labour = move.odex_labour_line_ids
            move.odex_parts_amount_untaxed = sum(parts.mapped('price_subtotal'))
            move.odex_parts_amount_total = sum(parts.mapped('price_total'))
            move.odex_parts_amount_tax = (
                move.odex_parts_amount_total - move.odex_parts_amount_untaxed)
            move.odex_labour_amount_untaxed = sum(labour.mapped('price_subtotal'))
            move.odex_labour_amount_total = sum(labour.mapped('price_total'))
            move.odex_labour_amount_tax = (
                move.odex_labour_amount_total - move.odex_labour_amount_untaxed)

    # @api.depends('partner_id', 'invoice_line_ids')
    # def _compute_odex_vehicle_info(self):
    #     for move in self:
    #         vehicle = move._odex_get_vehicle()
    #         move.odex_has_vehicle = bool(vehicle)
    #         move.odex_vehicle_license_plate = self._odex_read_first(
    #             vehicle, ('license_plate', 'license_plate_number',
    #                       'plate_number', 'number_plate', 'name', 'display_name'))
    #         move.odex_vehicle_make = self._odex_read_first(
    #             vehicle, ('make', 'make_id', 'brand', 'brand_id',
    #                       'manufacturer', 'manufacturer_id'))
    #         move.odex_vehicle_model = self._odex_read_first(
    #             vehicle, ('model', 'model_id', 'vehicle_model',
    #                       'vehicle_model_id'))
    #         move.odex_vehicle_variant = self._odex_read_first(
    #             vehicle, ('variant', 'variant_id', 'trim', 'trim_id',
    #                       'grade'))
    #         move.odex_vehicle_year = self._odex_read_first(
    #             vehicle, ('year', 'model_year', 'manufacturing_year',
    #                       'make_year'))
    #         move.odex_vehicle_chassis = self._odex_read_first(
    #             vehicle, ('chassis_number', 'chassis_no', 'chassis', 'vin',
    #                       'vin_sn', 'vin_number'))
    #         move.odex_vehicle_engine = self._odex_read_first(
    #             vehicle, ('engine_number', 'engine_no', 'engine',
    #                       'motor_number'))
    #         move.odex_vehicle_fuel_type = self._odex_read_first(
    #             vehicle, ('fuel_type', 'fuel', 'fuel_id'))
    #         move.odex_vehicle_transmission = self._odex_read_first(
    #             vehicle, ('transmission', 'transmission_type', 'gearbox',
    #                       'gear_type'))
    #         move.odex_vehicle_odometer = self._odex_read_first(
    #             vehicle, ('odometer', 'odometer_reading', 'mileage',
    #                       'current_odometer', 'last_odometer'))
    #         move.odex_vehicle_color = self._odex_read_first(
    #             vehicle, ('color', 'colour', 'vehicle_color', 'body_color'))

    @api.depends('name', 'state', 'company_id')
    def _compute_odex_qr_code(self):
        for move in self:
            move.odex_qr_code = False
            url = move._odex_portal_url()
            if not url:
                continue
            try:
                barcode = self.env['ir.actions.report'].barcode(
                    'QR', url, width=140, height=140, humanreadable=0)
                move.odex_qr_code = base64.b64encode(barcode)
            except Exception:  # pragma: no cover - never break the render
                _logger.info('ODEX invoice QR generation failed', exc_info=True)
                move.odex_qr_code = False

    # ------------------------------------------------------------------
    # Helpers
    #------------------------------------------------------------------
    # def _odex_get_vehicle(self):
    #     """Return the related vehicle record, or an empty recordset.

    #     Probes a direct vehicle relation on the move first, then a related
    #     job card. All lookups are guarded so a missing field never raises.
    #     """
    #     self.ensure_one()
    #     # 1) direct relation on the move
    #     for rel in _MOVE_VEHICLE_RELATIONS:
    #         rec = self._odex_getattr_record(self, rel)
    #         if rec:
    #             return rec[:1]
    #     # 2) via a related job card
    #     for rel in _MOVE_JOBCARD_RELATIONS:
    #         job = self._odex_getattr_record(self, rel)
    #         if job:
    #             for vrel in _JOBCARD_VEHICLE_RELATIONS:
    #                 rec = self._odex_getattr_record(job[:1], vrel)
    #                 if rec:
    #                     return rec[:1]
    #     return self.env['account.move'].browse()  # empty placeholder

    # @staticmethod
    # def _odex_getattr_record(record, name):
    #     """Safe getattr that only returns non-empty recordsets."""
    #     if not record or name not in record._fields:
    #         return None
    #     try:
    #         value = record[name]
    #     except Exception:
    #         return None
    #     if hasattr(value, '_name') and value:
    #         return value
    #     return None

    # @staticmethod
    # def _odex_read_first(record, names):
    #     """Return the first truthy value among candidate field names.

    #     Relational values are resolved to their display name; numeric and
    #     date values are cast to string. Returns ``False`` when nothing found.
    #     """
    #     if not record:
    #         return False
    #     for name in names:
    #         if name not in record._fields:
    #             continue
    #         try:
    #             value = record[name]
    #         except Exception:
    #             continue
    #         if value in (False, None, ''):
    #             continue
    #         # relational -> display name
    #         if hasattr(value, '_name'):
    #             if not value:
    #                 continue
    #             label = value[:1].display_name
    #             if label:
    #                 return label
    #             continue
    #         return str(value).strip()
    #     return False

    def _odex_portal_url(self):
        """Full, tokenised customer-portal URL for this invoice."""
        self.ensure_one()
        try:
            self._portal_ensure_token()
            token = self.access_token
            query = ('access_token=%s' % token) if token else None
            path = self.get_portal_url(query_string=('&%s' % query) if query else None)
            return self.get_base_url() + path
        except Exception:  # pragma: no cover
            _logger.info('ODEX portal URL build failed', exc_info=True)
            return False


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    odex_line_kind = fields.Selection(
        selection=[('parts', 'Parts'), ('labour', 'Labour')],
        string='ODEX Line Kind',
        compute='_compute_odex_line_kind',
        store=True, readonly=False,
        help="Classifies the invoice line for the enhanced workshop report. "
             "Auto-detected from the product (services / time-based lines are "
             "treated as Labour) and can be overridden manually or by the WMS.")
    odex_parts_type = fields.Selection(
        selection=[
            ('original', 'Original'),
            ('thijari', 'Thijari (Duplicate)'),
            ('used', 'Used'),
        ],
        string='Parts Type',
        compute='_compute_odex_parts_type',
        store=True, readonly=False,
        help="Origin of the part. Left empty for Labour lines.")
    odex_tax_amount = fields.Monetary(
        string='Tax Amount',
        compute='_compute_odex_tax_amount',
        compute_sudo=True,
        currency_field='currency_id')

    @api.depends('product_id', 'product_uom_id', 'display_type')
    def _compute_odex_line_kind(self):
        hour_uom = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        time_categ = self.env.ref('uom.uom_categ_wtime', raise_if_not_found=False)
        for line in self:
            if line.display_type and line.display_type != 'product':
                line.odex_line_kind = False
                continue
            product = line.product_id
            is_service = bool(product) and product.type == 'service'
            uom = line.product_uom_id
            is_time = bool(uom) and (
                (hour_uom and uom == hour_uom)
                or (time_categ and uom.category_id == time_categ))
            line.odex_line_kind = 'labour' if (is_service or is_time) else 'parts'

    @api.depends('odex_line_kind', 'product_id')
    def _compute_odex_parts_type(self):
        for line in self:
            if line.odex_line_kind == 'parts':
                # keep an explicit manual/WMS value, otherwise default
                line.odex_parts_type = line.odex_parts_type or 'original'
            else:
                line.odex_parts_type = False

    @api.depends('price_total', 'price_subtotal')
    def _compute_odex_tax_amount(self):
        for line in self:
            line.odex_tax_amount = line.price_total - line.price_subtotal
