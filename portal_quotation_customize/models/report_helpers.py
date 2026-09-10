# -*- coding: utf-8 -*-
"""Read-only helpers feeding the redesigned quotation report.

Nothing here stores data or changes business logic: every method resolves and
formats values that already exist on the order, the partner and the linked
inspection / vehicle records.
"""
from urllib.parse import quote

from odoo import models


# Vehicle attributes to print, in order. For each label a list of candidate
# technical field names is given: the first one that exists and holds a value
# wins. Field names differ between workshop modules, so the link is discovered
# by introspection instead of being hard-coded - override
# ``tus_get_vehicle_field_map`` to pin exact names.
VEHICLE_FIELD_MAP = [
    ("License Plate", ["license_plate", "plate_number", "plate_no", "vehicle_plate", "number_plate"]),
    ("Make", ["make_id", "brand_id", "vehicle_make_id", "make", "brand"]),
    ("Model", ["model_id", "vehicle_model_id", "car_model_id", "model"]),
    ("Variant", ["variant_id", "vehicle_variant_id", "variant", "trim"]),
    ("Year", ["year", "model_year", "manufacturing_year", "year_id", "make_year"]),
    ("Chassis Number", ["chassis_number", "chassis_no", "vin", "vin_number", "vin_no"]),
    ("Engine Number", ["engine_number", "engine_no"]),
    ("Fuel Type", ["fuel_type", "fuel_type_id", "fuel"]),
    ("Transmission", ["transmission", "transmission_type", "transmission_id", "gear_type"]),
    ("Odometer Reading", ["odometer", "odometer_reading", "current_odometer", "mileage", "km_reading"]),
    ("Color", ["color_id", "colour_id", "vehicle_color_id", "vehicle_colour_id", "vehicle_color", "colour"]),
]

# 'color' alone is skipped on purpose: in Odoo it is almost always the integer
# kanban colour index, not the paint colour.


class SaleOrderReport(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # Document identity
    # ------------------------------------------------------------------
    def tus_get_report_name(self):
        """Quotations print as Q00092 rather than S00092; confirmed orders keep
        their real name."""
        self.ensure_one()
        name = self.name or ""
        if self.state in ("draft", "sent") and name[:1].upper() == "S":
            return "Q" + name[1:]
        return name

    # ------------------------------------------------------------------
    # Parts / Labour split
    # ------------------------------------------------------------------
    def tus_is_labour_line(self, line):
        """Labour is identified by the product being a service.

        Isolated here so the rule can be repointed at a dedicated field
        without touching the report template.
        """
        return line.product_id.type == "service"

    def tus_get_report_sections(self):
        """Return the printable lines split into PARTS and LABOUR.

        Reuses ``tus_get_lines_to_report`` so the confirmed-only rule already
        implemented in the module keeps applying. Sections and notes are
        dropped: the document is split into its own two tables.
        """
        self.ensure_one()
        lines = self.tus_get_lines_to_report().filtered(
            lambda line: not line.display_type
        )
        return {
            "parts": lines.filtered(lambda line: not self.tus_is_labour_line(line)),
            "labour": lines.filtered(lambda line: self.tus_is_labour_line(line)),
        }

    def tus_get_report_summary(self):
        """Amounts for the bottom-right summary, derived from the printed lines
        so the document is always internally consistent."""
        self.ensure_one()
        sections = self.tus_get_report_sections()
        parts_untaxed = sum(sections["parts"].mapped("price_subtotal"))
        labour_untaxed = sum(sections["labour"].mapped("price_subtotal"))
        parts_total = sum(sections["parts"].mapped("price_total"))
        labour_total = sum(sections["labour"].mapped("price_total"))
        return {
            "parts_untaxed": parts_untaxed,
            "labour_untaxed": labour_untaxed,
            "parts_total": parts_total,
            "labour_total": labour_total,
            "subtotal": parts_untaxed + labour_untaxed,
            "tax": (parts_total + labour_total) - (parts_untaxed + labour_untaxed),
            "grand_total": parts_total + labour_total,
        }

    def tus_get_amount_in_words(self):
        """Grand total spelled out, using the currency's own converter."""
        self.ensure_one()
        summary = self.tus_get_report_summary()
        currency = self.currency_id or self.company_id.currency_id
        return currency.amount_to_text(summary["grand_total"])

    # ------------------------------------------------------------------
    # Customer card
    # ------------------------------------------------------------------
    def tus_get_customer_info(self):
        """(label, value) pairs for the customer card. Empty values are dropped
        by the caller, so the card only ever shows what exists."""
        self.ensure_one()
        partner = self.partner_id
        billing = self.partner_invoice_id or partner
        address_parts = [
            billing.street,
            billing.street2,
            " ".join(filter(None, [billing.city, billing.zip])),
            billing.state_id.name,
            billing.country_id.name,
        ]
        address = ", ".join(part.strip() for part in address_parts if part and part.strip())
        company = partner.parent_id.name or partner.company_name or ""
        values = [
            ("Customer Name", partner.name or ""),
            ("Company", company),
            ("Mobile", partner.mobile or partner.phone or ""),
            ("Email", partner.email or ""),
            ("Billing Address", address),
            ("TRN", partner.vat or ""),
        ]
        return [(label, value) for label, value in values if value]

    # ------------------------------------------------------------------
    # Vehicle card
    # ------------------------------------------------------------------
    def tus_get_vehicle_field_map(self):
        return VEHICLE_FIELD_MAP

    def tus_get_vehicle(self):
        """Resolve the vehicle record reachable from this order.

        Looks on the order itself first, then on the linked inspection, for a
        Many2one whose target carries a plate-like field.
        """
        self.ensure_one()
        plate_names = self.tus_get_vehicle_field_map()[0][1]
        for record in (self, self.tus_get_inspection()):
            if not record:
                continue
            for fname, field in record._fields.items():
                if field.type != "many2one" or field.comodel_name not in self.env:
                    continue
                comodel_fields = self.env[field.comodel_name]._fields
                if not any(name in comodel_fields for name in plate_names):
                    continue
                vehicle = record[fname]
                if vehicle:
                    return vehicle
        return self.env["sale.order"].browse()

    def _tus_read_display_value(self, record, fname):
        """Human-readable value of ``fname`` on ``record``, or '' when unset."""
        field = record._fields[fname]
        value = record[fname]
        if not value and value != 0:
            return ""
        if field.type == "many2one":
            return value.display_name or ""
        if field.type == "selection":
            return dict(field._description_selection(record.env)).get(value, value) or ""
        if field.type == "boolean":
            return "Yes" if value else ""
        if field.type in ("float", "monetary"):
            return "{:,.2f}".format(value) if value else ""
        if field.type == "integer":
            return "{:,}".format(value) if value else ""
        if field.type in ("date", "datetime"):
            return str(value)
        return str(value).strip()

    def tus_get_vehicle_info(self):
        """(label, value) pairs for the vehicle card, empty fields removed."""
        self.ensure_one()
        vehicle = self.tus_get_vehicle()
        inspection = self.tus_get_inspection()
        sources = [record for record in (vehicle, inspection, self) if record]

        info = []
        for label, candidates in self.tus_get_vehicle_field_map():
            value = ""
            for record in sources:
                for fname in candidates:
                    if fname not in record._fields:
                        continue
                    value = self._tus_read_display_value(record, fname)
                    if value:
                        break
                if value:
                    break
            if value:
                info.append((label, value))
        return info

    # ------------------------------------------------------------------
    # QR code
    # ------------------------------------------------------------------
    def tus_get_portal_qr_src(self):
        """Barcode-controller src for a QR of the customer portal share link.

        Nothing is hardcoded or stored: the URL is the order's own portal URL
        (access token included) and the image is rendered on the fly by Odoo's
        standard /report/barcode controller.
        """
        self.ensure_one()
        url = self.get_base_url() + self.get_portal_url()
        return (
            "/report/barcode/?barcode_type=QR&value=%s&width=180&height=180&"
            "humanreadable=0" % quote(url, safe="")
        )
