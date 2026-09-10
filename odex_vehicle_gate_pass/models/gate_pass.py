# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Workflow, in order. Everything else derives from this single list.
FLOW_STEPS = [
    ("gatepass_in", "Gatepass In", "fa-sign-in"),
    ("vehicle", "Vehicle", "fa-car"),
    ("inspection", "Inspection", "fa-search"),
    ("rfq", "RFQ", "fa-handshake-o"),
    ("purchase", "Purchase",  "fa-handshake-o"),
    ("quotation", "Quotation", "fa-file-text-o"),  
    ("jobcard", "Jobcard", "fa-wrench"),
    ("invoice", "Invoice", "fa-file-o"),
    ("gatepass_out", "Gatepass Out", "fa-sign-out"),
]
FLOW_KEYS = [step[0] for step in FLOW_STEPS]

# Candidate technical names for modules that may or may not be installed here.
# Nothing is assumed: every one of these is checked against the live registry
# before it is used, and the model degrades gracefully when none matches.
BOOKING_MODEL_CANDIDATES = [
    "odex.workshop.booking",
    "odex.booking",
    "workshop.booking",
    "garage.booking",
    "vehicle.booking",
    "fleet.vehicle.booking",
    "service.booking",
]
JOB_CARD_MODEL_CANDIDATES = [
    # "odex.job.card",
    # "job.card",
    # "workshop.job.card",
    # "garage.job.card",
    # "fleet.job.card",
    "project.task",
]
# fleet.vehicle field names differ between plain Odoo and customised databases.
VEHICLE_FIELD_CANDIDATES = {
    "registration_no": ["license_plate", "registration_no", "plate_no"],
    "chassis_no": ["vin_sn", "chassis_no", "vin", "chassis_number"],
    "engine_no": ["engine_no", "engine_number", "x_engine_no"],
    "brand": ["vehicle_make_id", "brand_id", "make_id"],
    "vehicle_model": ["model_id"],
    "manufacturing_year": ["model_year", "year", "manufacturing_year"],
    "color": ["color_id", "vehicle_color_id", "color"],
    "fuel_type": ["fuel_type"],
    "transmission": ["transmission"],
    "engine_capacity": ["engine_size", "engine_capacity", "horsepower"],
    "odometer": ["odometer"],
    "customer_id": ["partner_id"],
}


class OdexGatePass(models.Model):
    _name = "odex.gate.pass"
    _description = "Vehicle Gate Pass"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Gate Pass No.",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
    )
    gate_pass_no = fields.Char(
        string="Gate Pass Number",
        compute="_compute_gate_pass_no",
        store=True,
        readonly=True,
        help="Mirror of the gate pass number, kept for reporting and integrations.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    date_in = fields.Datetime(
        string="Date In", default=fields.Datetime.now, tracking=True, copy=False
    )
    date_out = fields.Datetime(string="Date Out", readonly=True, copy=False, tracking=True)
    time_in = fields.Char(string="Time In", compute="_compute_times")
    time_out = fields.Char(string="Time Out", compute="_compute_times")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("gatepass_in", "Gatepass In"),
            ("vehicle", "Vehicle"),
            ("inspection", "Inspection"),
            ("rfq", "RFQ"),
            ("purchase", "Purchase"),
            ("quotation", "Quotation"), 
            ("jobcard", "Jobcard"),
            ("invoice", "Invoice"),
            ("gatepass_out", "Gatepass Out"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    location_label = fields.Char(string="Location", compute="_compute_location_label")
    flow_json = fields.Char(compute="_compute_flow_json")

    # ------------------------------------------------------------------
    # Booking - resolved at runtime, no hard dependency on a booking module
    # ------------------------------------------------------------------
    booking_status = fields.Selection(
        [("not_booked", "Not Booked"), ("booked", "Booked"), ("cancelled", "Cancelled")],
        string="Booking Status",
        default="not_booked",
        tracking=True,
    )
    booking_model = fields.Char(string="Booking Model", readonly=True, copy=False)
    booking_id = fields.Many2oneReference(
        string="Booking", model_field="booking_model", readonly=True, copy=False
    )
    booking_no = fields.Char(string="Booking No.", copy=False)
    booking_date = fields.Date(string="Booking Date", copy=False)
    customer_requested_date = fields.Date(string="Requested Date")
    customer_requested_time = fields.Char(string="Requested Time")

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------
    customer_id = fields.Many2one(
        "res.partner", string="Customer", tracking=True, index=True
    )
    # customer_name = fields.Char(string="Customer Name")
    mobile_no = fields.Char(string="Mobile No.")
    email = fields.Char(string="Email ID")
    alternative_contact = fields.Char(string="Alternative Contact")
    tag_ids = fields.Many2many("res.partner.category", string="Tags")
    customer_waiting = fields.Boolean(string="Customer Waiting")
    # business = fields.Char(string="Business")
    repair_category_id = fields.Many2one(
        'repair.category.custom',
        string="Business"
    )
    repair_sub_category_ids = fields.Many2many('repair.sub.category.custom', 'repair_sub_category_custom_gatepass_rel',
                                               'sub_category_id', 'task_id', string="Type")
    # job_type = fields.Char(string="Job Type")
    # job_bay = fields.Char(string="Job Bay")

    # ------------------------------------------------------------------
    # Vehicle
    # ------------------------------------------------------------------
    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle", tracking=True, index=True)
    registration_no = fields.Char(string="Registration No.", index=True, tracking=True)
    chassis_no = fields.Char(string="Chassis No.", index=True)
    engine_no = fields.Char(string="Engine No.")
    brand = fields.Char(string="Brand")
    vehicle_model = fields.Char(string="Model")
    manufacturing_year = fields.Char(string="Manufacturing Year")
    color = fields.Char(string="Color")
    fuel_type = fields.Char(string="Fuel Type")
    transmission = fields.Char(string="Transmission")
    engine_capacity = fields.Char(string="Engine Capacity")
    cylinder_count = fields.Integer(string="Cylinder Count")
    # warranty = fields.Char(string="Warranty")
    plate_source = fields.Char(string="Plate Source")

    # ------------------------------------------------------------------
    # Vehicle condition
    # ------------------------------------------------------------------
    overall_condition = fields.Selection(
        [("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
        string="Vehicle Condition",
        default="good",
    )
    fuel_level = fields.Selection(
        [("empty", "Empty"), ("quarter", "1/4"), ("half", "1/2"),
         ("three_quarter", "3/4"), ("full", "Full")],
        string="Fuel Level",
        default="half",
    )
    visible_damage = fields.Selection(
        [("no", "No"), ("yes", "Yes")], string="Visible Damage", default="no"
    )
    tyre_condition = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
        string="Tyre Condition",
        default="good",
    )
    accessories = fields.Selection(
        [("all_available", "All Available"), ("some_missing", "Some Missing"),
         ("not_checked", "Not Checked")],
        string="Accessories",
        default="all_available",
    )
    odometer_reading = fields.Float(string="Odometer Reading (KM)")
    additional_remarks = fields.Text(string="Additional Remarks")

    ac_cooling = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor"), ("not_checked", "Not Checked")],
        string="A/C Cooling",
        default="good",
    )
    battery_health = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor"), ("not_checked", "Not Checked")],
        string="Battery Health",
        default="good",
    )
    lights_indicators = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor"), ("not_checked", "Not Checked")],
        string="Lights & Indicators",
        default="good",
    )
    other_electrical = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor"), ("not_checked", "Not Checked")],
        string="Other Electrical",
        default="good",
    )
    overall_status_label = fields.Char(compute="_compute_overall_status_label")

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    photo_ids = fields.One2many("odex.gate.pass.photo", "gate_pass_id", string="Photos")
    damage_ids = fields.One2many("odex.gate.pass.damage", "gate_pass_id", string="Damage Markers")
    timeline_ids = fields.One2many(
        "odex.gate.pass.timeline", "gate_pass_id", string="Timeline"
    )
    requested_services_ids = fields.One2many('job.requested.service', 'gate_pass_id', 'Requested Services')
    # inspection_ids = fields.One2many(
    #     "odex.gate.pass.inspection", "gate_pass_id", string="Inspection Checklist"
    # )
    photo_count = fields.Integer(compute="_compute_counts")
    damage_count = fields.Integer(compute="_compute_counts")

    # ------------------------------------------------------------------
    # Quotation / RFQ / Job card - runtime references
    # ------------------------------------------------------------------
    quotation_model = fields.Char(readonly=True, copy=False)
    quotation_id = fields.Many2oneReference(
        string="Quotation", model_field="quotation_model", readonly=True, copy=False
    )
    quotation_no = fields.Char(string="Quotation No.", readonly=True, copy=False)
    quotation_amount = fields.Monetary(
        string="Quotation Amount", currency_field="currency_id", readonly=True, copy=False
    )

    rfq_model = fields.Char(readonly=True, copy=False)
    rfq_id = fields.Many2oneReference(
        string="RFQ", model_field="rfq_model", readonly=True, copy=False
    )
    rfq_no = fields.Char(string="RFQ No.", readonly=True, copy=False)

    job_card_model = fields.Char(readonly=True, copy=False)
    job_card_id = fields.Many2oneReference(
        string="Job Card", model_field="job_card_model", readonly=True, copy=False
    )
    job_card_no = fields.Char(string="Job Card No.", readonly=True, copy=False)
    job_card_status = fields.Char(string="Job Card Status", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Invoice and payment
    # ------------------------------------------------------------------
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain="[('move_type', '=', 'out_invoice')]",
        copy=False,
    )
    invoice_no = fields.Char(
        string="Invoice No.", compute="_compute_payment", store=True, readonly=True
    )
    invoice_amount = fields.Monetary(
        string="Invoice Amount", currency_field="currency_id",
        compute="_compute_payment", store=True, readonly=True,
    )
    paid_amount = fields.Monetary(
        string="Paid Amount", currency_field="currency_id",
        compute="_compute_payment", store=True, readonly=True,
    )
    due_amount = fields.Monetary(
        string="Due Amount", currency_field="currency_id",
        compute="_compute_payment", store=True, readonly=True,
    )
    payment_status = fields.Selection(
        [("not_invoiced", "Not Invoiced"), ("unpaid", "Unpaid"),
         ("partial", "Partial"), ("paid", "Paid")],
        string="Payment Status",
        compute="_compute_payment",
        store=True,
        readonly=True,
        default="not_invoiced",
    )

    # ------------------------------------------------------------------
    # Signature
    # ------------------------------------------------------------------
    signature = fields.Binary(string="Customer Signature", attachment=True, copy=False)
    signed_by = fields.Char(string="Signed By", copy=False)
    signed_at = fields.Datetime(string="Signed On", readonly=True, copy=False)
    count_inspection = fields.Integer(string="Count Inspection", compute="_count_jobcard_inspection")
    count_jobcard = fields.Integer(string="Count Jobcard", compute="_count_jobcard_inspection")
    count_sales = fields.Integer(string="Quotaion", compute="_count_jobcard_inspection") 
    count_invoices = fields.Integer(string="Invoices", compute="_count_jobcard_inspection") 

    _sql_constraints = [
        (
            "gate_pass_name_company_uniq",
            "unique(name, company_id)",
            "The gate pass number must be unique per company.",
        ),
    ]

    # ==================================================================
    # Computes
    # ==================================================================
    def _count_jobcard_inspection(self):
        for rec in self:
            job_card = self.env['project.task'].search([('vehicle_id', '=', rec.vehicle_id.id), ('is_jobcard', '=', True)])
            vehicle_inspection = self.env['project.task'].search([('vehicle_id', '=', rec.vehicle_id.id), ('is_vc', '=', True)])
            sales_count = self.env['sale.order'].search([('vehicle_id', '=', rec.vehicle_id.id)])
            invoice_count = self.env['account.move'].search([('vehicle_id', '=', rec.vehicle_id.id), ('move_type', '=', 'out_invoice')])
            rec.count_jobcard = len(job_card.ids)
            rec.count_inspection = len(vehicle_inspection.ids)
            rec.count_sales = len(sales_count)
            rec.count_invoices = len(invoice_count)

    @api.depends("name")
    def _compute_gate_pass_no(self):
        for record in self:
            record.gate_pass_no = record.name

    @api.depends("customer_id", "name", "registration_no")
    def _compute_display_name(self):
        for record in self:
            parts = [record.name or ""]
            if record.registration_no:
                parts.append(record.registration_no)
            record.display_name = " - ".join(part for part in parts if part)

    @api.depends("date_in", "date_out")
    def _compute_times(self):
        for record in self:
            record.time_in = record._format_time(record.date_in)
            record.time_out = record._format_time(record.date_out)

    def _format_time(self, value):
        if not value:
            return "-"
        return fields.Datetime.context_timestamp(self, value).strftime("%d-%b-%Y %I:%M %p")

    @api.depends("state")
    def _compute_location_label(self):
        for record in self:
            if record.state in ("draft",):
                record.location_label = _("Not Started")
            elif record.state == "cancelled":
                record.location_label = _("Cancelled")
            elif record.state == "gatepass_out":
                record.location_label = _("Left Workshop")
            else:
                record.location_label = _("Inside Workshop")

    @api.depends("state")
    def _compute_flow_json(self):
        for record in self:
            current = record.state
            if current in ("draft", "cancelled"):
                current_index = -1
            else:
                current_index = FLOW_KEYS.index(current)
            steps = []
            for index, (key, label, icon) in enumerate(FLOW_STEPS):
                if index < current_index:
                    status = "done"
                elif index == current_index:
                    status = "current"
                else:
                    status = "pending"
                steps.append({
                    "key": key,
                    "label": label,
                    "icon": icon,
                    "status": status,
                    "clickable": index == current_index + 1 and record.state != "cancelled",
                })
            record.flow_json = json.dumps(steps)

    @api.depends("overall_condition")
    def _compute_overall_status_label(self):
        labels = dict(self._fields["overall_condition"].selection)
        for record in self:
            record.overall_status_label = labels.get(record.overall_condition, _("Not Set"))

    @api.depends("photo_ids", "damage_ids")
    def _compute_counts(self):
        for record in self:
            record.photo_count = len(record.photo_ids)
            record.damage_count = len(record.damage_ids)

    @api.depends(
        "invoice_id",
        "invoice_id.state",
        "invoice_id.amount_total",
        "invoice_id.amount_residual",
        "invoice_id.payment_state",
        "invoice_id.name",
    )
    def _compute_payment(self):
        for record in self:
            invoice = record.invoice_id
            if not invoice or invoice.state == "cancel":
                record.invoice_no = False
                record.invoice_amount = 0.0
                record.paid_amount = 0.0
                record.due_amount = 0.0
                record.payment_status = "not_invoiced"
                continue
            total = invoice.amount_total
            due = invoice.amount_residual
            paid = total - due
            record.invoice_no = invoice.name
            record.invoice_amount = total
            record.paid_amount = paid
            record.due_amount = due
            if invoice.currency_id.is_zero(due):
                record.payment_status = "paid"
            elif paid > 0:
                record.payment_status = "partial"
            else:
                record.payment_status = "unpaid"

    # ==================================================================
    # Normalisation, constraints, CRUD
    # ==================================================================
    @api.model
    def _normalize_values(self, values):
        service = self.env["odex.ocr.service"]
        if values.get("registration_no"):
            values["registration_no"] = service.normalize_plate(values["registration_no"])
        if values.get("chassis_no"):
            values["chassis_no"] = service.normalize_vin(values["chassis_no"])
        if values.get("engine_no"):
            values["engine_no"] = re.sub(r"\s+", "", values["engine_no"]).upper()
        return values

    @api.constrains("odometer_reading")
    def _check_odometer(self):
        for record in self:
            if record.odometer_reading < 0:
                raise ValidationError(_("The odometer reading cannot be negative."))

    @api.constrains("date_in", "date_out")
    def _check_dates(self):
        for record in self:
            if record.date_in and record.date_out and record.date_out < record.date_in:
                raise ValidationError(_("Date Out cannot be earlier than Date In."))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._normalize_values(values)
            if not values.get("name") or values["name"] == _("New"):
                sequence = self.env["ir.sequence"].next_by_code("odex.gate.pass")
                values["name"] = sequence or _("New")
        records = super().create(vals_list)
        for record in records:
            record._build_timeline()
            record._auto_link_booking()
            if record.odometer_reading and record.vehicle_id:
                record._sync_fleet_odometer()
        return records

    def write(self, values):
        self._normalize_values(values)
        result = super().write(values)
        if "odometer_reading" in values:
            for record in self:
                record._sync_fleet_odometer()
        return result

    def copy_data(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        return super().copy_data(default)

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "cancelled"):
                raise UserError(
                    _("Gate pass %s is in progress. Cancel it before deleting.") % record.name
                )
        return super().unlink()

    # ==================================================================
    # Onchange
    # ==================================================================
    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        for record in self:
            if record.customer_id:
                partner = record.customer_id
                # record.customer_name = partner.name
                record.mobile_no = partner.mobile or partner.phone or ""
                record.email = partner.email or ""
                if partner.category_id:
                    record.tag_ids = [(6, 0, partner.category_id.ids)]

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        for record in self:
            if record.vehicle_id:
                record._fill_from_vehicle(record.vehicle_id)

    # ==================================================================
    # Fleet helpers - every field name is probed before it is read
    # ==================================================================
    @api.model
    def _vehicle_field(self, key):
        """Return the first candidate field that actually exists on fleet.vehicle."""
        vehicle_fields = self.env["fleet.vehicle"]._fields
        for candidate in VEHICLE_FIELD_CANDIDATES.get(key, []):
            if candidate in vehicle_fields:
                return candidate
        return False

    @api.model
    def _vehicle_value(self, vehicle, key):
        field_name = self._vehicle_field(key)
        if not field_name:
            return ""
        try:
            value = vehicle[field_name]
        except (KeyError, AttributeError):
            return ""
        if isinstance(value, models.BaseModel):
            return value.display_name if value else ""
        if value is False or value is None:
            return ""
        return value

    def _fill_from_vehicle(self, vehicle):
        self.ensure_one()
        if not vehicle:
            return
        self.registration_no = self._vehicle_value(vehicle, "registration_no") or self.registration_no
        self.chassis_no = self._vehicle_value(vehicle, "chassis_no") or self.chassis_no
        self.engine_no = self._vehicle_value(vehicle, "engine_no") or self.engine_no
        self.brand = self._vehicle_value(vehicle, "brand") or self.brand
        self.vehicle_model = self._vehicle_value(vehicle, "vehicle_model") or self.vehicle_model
        year = self._vehicle_value(vehicle, "manufacturing_year")
        self.manufacturing_year = str(year) if year else self.manufacturing_year
        self.color = self._vehicle_value(vehicle, "color") or self.color
        self.fuel_type = self._vehicle_value(vehicle, "fuel_type") or self.fuel_type
        self.transmission = self._vehicle_value(vehicle, "transmission") or self.transmission
        capacity = self._vehicle_value(vehicle, "engine_capacity")
        self.engine_capacity = str(capacity) if capacity else self.engine_capacity
        odo = self._vehicle_value(vehicle, "odometer")
        if odo:
            self.odometer_reading = odo
        self.customer_id = self._vehicle_value(vehicle, "customer_id") or self.customer_id
        if not self.customer_id:
            partner_field = self._vehicle_field("customer_id")
            partner = vehicle[partner_field] if partner_field else False
            if partner:
                self.customer_id = partner.id
                self._onchange_customer_id()

    def _sync_fleet_odometer(self):
        """Log the gate pass odometer reading back to the fleet vehicle.

        Fleet keeps odometer history in fleet.vehicle.odometer; the vehicle's
        `odometer` field is the latest of those. We only add a log when the
        reading is a real, different value so we don't spam duplicate entries.
        """
        self.ensure_one()
        if not self.vehicle_id or not self.odometer_reading:
            return
        if "fleet.vehicle.odometer" not in self.env:
            return
        field_name = self._vehicle_field("odometer")
        current = 0.0
        if field_name:
            try:
                current = self.vehicle_id[field_name] or 0.0
            except (KeyError, AttributeError):
                current = 0.0
        if float_compare(self.odometer_reading, current, precision_digits=2) == 0:
            return
        try:
            self.env["fleet.vehicle.odometer"].sudo().create({
                "vehicle_id": self.vehicle_id.id,
                "value": self.odometer_reading,
                "date": fields.Date.context_today(self),
            })
            _logger.info(
                "Gate Pass %s: logged odometer %s to fleet vehicle %s",
                self.name, self.odometer_reading, self.vehicle_id.display_name,
            )
        except Exception as err:  # noqa: BLE001 - fleet write must never block the gate pass
            _logger.warning("Gate Pass %s: fleet odometer log failed (%s)", self.name, err)

    @api.model
    def _search_vehicle(self, registration_no=None, chassis_no=None):
        """Find a fleet vehicle by plate or VIN. Returns a recordset (may be empty)."""
        Vehicle = self.env["fleet.vehicle"]
        service = self.env["odex.ocr.service"]
        if chassis_no:
            field_name = self._vehicle_field("chassis_no")
            if field_name:
                vin = service.normalize_vin(chassis_no)
                vehicle = Vehicle.search([(field_name, "=ilike", vin)], limit=1)
                if vehicle:
                    return vehicle
        if registration_no:
            field_name = self._vehicle_field("registration_no")
            if field_name:
                plate = service.normalize_plate(registration_no)
                vehicle = Vehicle.search([(field_name, "=ilike", plate)], limit=1)
                if vehicle:
                    return vehicle
                stripped = re.sub(r"[^A-Z0-9]", "", plate.upper())
                if stripped:
                    for candidate in Vehicle.search(
                        [(field_name, "!=", False)], limit=2000
                    ):
                        value = candidate[field_name] or ""
                        if re.sub(r"[^A-Z0-9]", "", value.upper()) == stripped:
                            return candidate
        return Vehicle.browse()

    def action_lookup_vehicle(self):
        """Fill the form from fleet using whatever identifier is present."""
        self.ensure_one()
        vehicle = self._search_vehicle(self.registration_no, self.chassis_no)
        if not vehicle:
            _logger.info("Gate Pass %s: no fleet vehicle for plate=%s vin=%s",
                         self.name, self.registration_no, self.chassis_no)
            return self._notify(
                _("Vehicle not found"),
                _("No vehicle matches this registration or chassis number. "
                  "Use Create Vehicle to add it to the fleet."),
                "warning",
            )
        self.vehicle_id = vehicle.id
        self._fill_from_vehicle(vehicle)
        _logger.info("Gate Pass %s: matched fleet vehicle %s", self.name, vehicle.display_name)
        return self._notify(
            _("Vehicle matched"), _("Loaded %s from the fleet.") % vehicle.display_name, "success"
        )

    def action_create_vehicle(self):
        """Create the fleet vehicle from what is on screen. Never duplicates."""
        self.ensure_one()
        existing = self._search_vehicle(self.registration_no, self.chassis_no)
        if existing:
            self.vehicle_id = existing.id
            self._fill_from_vehicle(existing)
            return self._notify(
                _("Vehicle already exists"),
                _("Linked to the existing record %s.") % existing.display_name,
                "info",
            )
        if not self.registration_no and not self.chassis_no:
            raise UserError(
                _("Enter a registration number or a chassis number before creating a vehicle.")
            )
        values = {}
        plate_field = self._vehicle_field("registration_no")
        if plate_field and self.registration_no:
            values[plate_field] = self.registration_no
        vin_field = self._vehicle_field("chassis_no")
        if vin_field and self.chassis_no:
            values[vin_field] = self.chassis_no
        partner_field = self._vehicle_field("customer_id")
        if partner_field and self.customer_id:
            values[partner_field] = self.customer_id.id
        model_field = self._vehicle_field("vehicle_model")
        if model_field and not values.get(model_field):
            model = self.env["fleet.vehicle.model"].search([], limit=1)
            if not model:
                raise UserError(
                    _("Fleet has no vehicle model yet. Create one under Fleet > Configuration "
                      "> Models, then try again.")
                )
            values[model_field] = model.id
        vehicle = self.env["fleet.vehicle"].create(values)
        self.vehicle_id = vehicle.id
        self._fill_from_vehicle(vehicle)
        _logger.info("Gate Pass %s: created fleet vehicle %s", self.name, vehicle.display_name)
        return self._notify(
            _("Vehicle created"), _("%s was added to the fleet.") % vehicle.display_name, "success"
        )

    def action_create_customer(self):
        self.ensure_one()
        if self.customer_id:
            raise UserError(_("This gate pass already has a customer."))
        # if not self.customer_name:
        #     raise UserError(_("Enter the customer name first."))
        # domain = [("name", "=ilike", self.customer_name)]
        domain = [("name", "=ilike", self.customer_id.name)]
        if self.mobile_no:
            domain = ["|", ("mobile", "=", self.mobile_no), ("phone", "=", self.mobile_no)]
        existing = self.env["res.partner"].search(domain, limit=1)
        if existing:
            self.customer_id = existing.id
            self._onchange_customer_id()
            return self._notify(
                _("Customer already exists"),
                _("Linked to %s.") % existing.display_name,
                "info",
            )
        partner = self.env["res.partner"].create({
            # "name": self.customer_name,
            "name": self.customer_id.name,
            "mobile": self.mobile_no or False,
            "email": self.email or False,
            "phone": self.alternative_contact or False,
        })
        self.customer_id = partner.id
        return self._notify(
            _("Customer created"), _("%s was added.") % partner.display_name, "success"
        )

    # ==================================================================
    # OCR entry points called from the browser
    # ==================================================================
    @api.model
    def ocr_status(self):
        return self.env["odex.ocr.service"].get_status()

    def ocr_scan_plate(self, image):
        """Read a plate and report what it matches. Does not write anything yet."""
        self.ensure_one()
        result = self.env["odex.ocr.service"].scan_registration_plate(image)
        result["match"] = self._match_preview(registration_no=result.get("registration_no"))
        return result

    def ocr_scan_mulkiya(self, image):
        self.ensure_one()
        result = self.env["odex.ocr.service"].scan_mulkiya(image)
        result["match"] = self._match_preview(
            registration_no=result.get("registration_no"),
            chassis_no=result.get("chassis_no"),
        )
        return result

    def _match_preview(self, registration_no=None, chassis_no=None):
        vehicle = self._search_vehicle(registration_no, chassis_no)
        if not vehicle:
            return {"found": False}
        return {
            "found": True,
            "id": vehicle.id,
            "display_name": vehicle.display_name,
        }

    def apply_scan_result(self, values):
        """Confirm an OCR result: write it, then pull the fleet record if it exists."""
        self.ensure_one()
        allowed = {
            "registration_no", "chassis_no", "engine_no", "brand", "vehicle_model",
            "manufacturing_year", "color", "fuel_type", "transmission", "plate_source",
        }
        payload = {key: value for key, value in (values or {}).items()
                   if key in allowed and value}
        if not payload:
            raise UserError(_("Nothing was detected in this image. Try again."))
        self.write(payload)
        vehicle = self._search_vehicle(self.registration_no, self.chassis_no)
        if vehicle:
            self.vehicle_id = vehicle.id
            self._fill_from_vehicle(vehicle)
            return {"vehicle_found": True, "vehicle_name": vehicle.display_name}
        return {"vehicle_found": False}

    # ==================================================================
    # Timeline
    # ==================================================================
    def _build_timeline(self):
        self.ensure_one()
        Timeline = self.env["odex.gate.pass.timeline"]
        existing = set(self.timeline_ids.mapped("step"))
        rows = []
        for sequence, (key, label, _icon) in enumerate(FLOW_STEPS, start=1):
            if key in existing:
                continue
            rows.append({
                "gate_pass_id": self.id,
                "step": key,
                "sequence": sequence * 10,
            })
        if rows:
            Timeline.create(rows)

    def _mark_timeline(self, step, ref_model=False, ref_id=False, note=False):
        self.ensure_one()
        line = self.timeline_ids.filtered(lambda item: item.step == step)
        if not line:
            self._build_timeline()
            line = self.timeline_ids.filtered(lambda item: item.step == step)
        line.write({
            "status": "done",
            "date": fields.Datetime.now(),
            "user_id": self.env.user.id,
            "ref_model": ref_model or False,
            "ref_id": ref_id or False,
            "note": note or False,
        })

    # ==================================================================
    # Workflow
    # ==================================================================
    def _advance(self, step):
        self.ensure_one()
        if self.state == "cancelled":
            raise UserError(_("This gate pass is cancelled. Reset it to draft first."))
        target_index = FLOW_KEYS.index(step)
        current_index = FLOW_KEYS.index(self.state) if self.state in FLOW_KEYS else -1
        if target_index > current_index + 1:
            missing = FLOW_STEPS[current_index + 1][1]
            raise UserError(
                _("Complete %s before moving to %s.") % (missing, FLOW_STEPS[target_index][1])
            )
        self.state = step
        self._mark_timeline(step)
        _logger.info("Gate Pass %s: state -> %s", self.name, step)

    def action_gatepass_in(self):
        for record in self:
            if not record.registration_no and not record.vehicle_id:
                raise UserError(
                    _("Enter the registration number or select a vehicle before checking in.")
                )
            if not record.date_in:
                record.date_in = fields.Datetime.now()
            record._advance("gatepass_in")
        return True

    def action_vehicle(self):
        for record in self:
            if not record.vehicle_id:
                raise UserError(
                    _("Link a fleet vehicle first. Use Scan Plate, Scan VIN or Find Vehicle.")
                )
            record._sync_fleet_odometer()
            record._advance("vehicle")
        return True

    def action_inspection(self):
        for record in self:
            record._advance("inspection")
        return True

    def action_quotation(self):
        for record in self:
            record._sync_quotation()
            record._advance("quotation")
        return True

    def action_purchase(self):
        for record in self:
            # record._sync_quotation()
            record._advance("purchase")
        return True

    def action_rfq(self):
        for record in self:
            record._sync_rfq()
            record._advance("rfq")
        return True

    def action_jobcard(self):
        for record in self:
            record._sync_job_card()
            record._advance("jobcard")
        return True

    def action_invoice(self):
        for record in self:
            record._sync_invoice()
            record._advance("invoice")
        return True

    def action_gatepass_out(self):
        for record in self:
            record._check_gatepass_out()
            record.date_out = fields.Datetime.now()
            record._advance("gatepass_out")
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_draft(self):
        for record in self:
            record.state = "draft"
            record.timeline_ids.write({
                "status": "pending", "date": False, "user_id": False,
                "ref_model": False, "ref_id": False,
            })
        return True

    def action_flow_step(self, step):
        """Called by the flow bar in the browser."""
        self.ensure_one()
        handlers = {
            "gatepass_in": self.action_gatepass_in,
            "vehicle": self.action_vehicle,
            "inspection": self.action_inspection,
            "quotation": self.action_quotation,
            "rfq": self.action_rfq,
            "jobcard": self.action_jobcard,
            "invoice": self.action_invoice,
            "gatepass_out": self.action_gatepass_out,
        }
        handler = handlers.get(step)
        if not handler:
            raise UserError(_("Unknown workflow step: %s") % step)
        return handler()

    def _check_gatepass_out(self):
        self.ensure_one()
        problems = []
        if not self.vehicle_id:
            problems.append(_("the vehicle is not identified"))
        if not self.customer_id:
            problems.append(_("the customer is not identified"))
        if not self.name or self.name == _("New"):
            problems.append(_("the gate pass has no number"))

        params = self.env["ir.config_parameter"].sudo()
        require_inspection = params.get_param(
            "odex_vehicle_gate_pass.require_inspection", "1"
        ) in ("1", "True", "true")
        require_payment = params.get_param(
            "odex_vehicle_gate_pass.require_payment", "0"
        ) in ("1", "True", "true")
        block_major_damage = params.get_param(
            "odex_vehicle_gate_pass.block_major_damage", "0"
        ) in ("1", "True", "true")

        if require_inspection:
            done = self.timeline_ids.filtered(
                lambda line: line.step == "inspection" and line.status == "done"
            )
            if not done:
                problems.append(_("the inspection step is not completed"))
        if require_payment and self.payment_status in ("unpaid", "partial", "not_invoiced"):
            problems.append(_("the invoice is not fully paid"))
        if block_major_damage:
            unresolved = self.damage_ids.filtered(
                lambda damage: damage.severity == "major" and not damage.resolved
            )
            if unresolved:
                problems.append(
                    _("%s major damage marker(s) are still unresolved") % len(unresolved)
                )
        if problems:
            raise UserError(
                _("This vehicle cannot leave yet because %s.") % ", ".join(problems)
            )

    # ==================================================================
    # Runtime integrations - booking, quotation, RFQ, job card, invoice
    # ==================================================================
    @api.model
    def _resolve_model(self, candidates, keyword=None):
        """Return the first candidate model present in the registry, else False."""
        for candidate in candidates:
            if candidate in self.env:
                return candidate
        if keyword:
            found = self.env["ir.model"].sudo().search(
                [("model", "like", keyword)], limit=1
            )
            if found and found.model in self.env:
                return found.model
        return False

    @api.model
    def _booking_model_name(self):
        return self._resolve_model(BOOKING_MODEL_CANDIDATES, keyword="booking")

    def _auto_link_booking(self):
        """Attach an existing booking when a booking module is installed."""
        self.ensure_one()
        model_name = self._booking_model_name()
        if not model_name:
            return False
        Booking = self.env[model_name]
        booking_fields = Booking._fields
        domain = []
        if self.vehicle_id and "vehicle_id" in booking_fields:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        elif self.customer_id and "partner_id" in booking_fields:
            domain.append(("partner_id", "=", self.customer_id.id))
        else:
            return False
        try:
            booking = Booking.search(domain, limit=1, order="id desc")
        except Exception as err:  # noqa: BLE001 - a foreign model must never break create()
            _logger.warning("Gate Pass: booking lookup on %s failed (%s)", model_name, err)
            return False
        if not booking:
            return False
        self.booking_model = model_name
        self.booking_id = booking.id
        self.booking_no = booking.name
        # for candidate in ("booking_date", "date", "schedule_date", "create_date"):
        #     if candidate in booking_fields and booking[candidate]:
        #         self.booking_date = booking[candidate]
        #         break
        self.booking_date = booking.booking_date
        self.booking_status = "booked"
        _logger.info("Gate Pass %s: linked booking %s (%s)", self.name, booking.id, model_name)
        return True

    def _sync_quotation(self):
        self.ensure_one()
        if "sale.order" not in self.env:
            return False
        domain = [("state", "in", ("draft", "sent", "sale"))]
        if self.customer_id:
            domain.append(("partner_id", "=", self.customer_id.id))
        else:
            return False
        order = self.env["sale.order"].search(domain, limit=1, order="id desc")
        if not order:
            return False
        self.quotation_model = "sale.order"
        self.quotation_id = order.id
        self.quotation_no = order.name
        self.quotation_amount = order.amount_total
        return True

    def _sync_rfq(self):
        self.ensure_one()
        if "purchase.order" not in self.env:
            return False
        order = self.env["purchase.order"].search(
            [("state", "in", ("draft", "sent", "purchase"))], limit=1, order="id desc"
        )
        if not order:
            return False
        self.rfq_model = "purchase.order"
        self.rfq_id = order.id
        self.rfq_no = order.name
        return True

    def _sync_job_card(self):
        self.ensure_one()
        model_name = self._resolve_model(JOB_CARD_MODEL_CANDIDATES, keyword="job.card")
        if not model_name:
            return False
        JobCard = self.env[model_name]
        job_fields = JobCard._fields
        domain = []
        # project.task is only a job card when the workshop flag says so.
        if model_name == "project.task":
            if "is_jobcard" in job_fields:
                domain.append(("is_jobcard", "=", True))
            else:
                return False
        if self.vehicle_id and "vehicle_id" in job_fields:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        elif self.customer_id and "partner_id" in job_fields:
            domain.append(("partner_id", "=", self.customer_id.id))
        else:
            return False
        try:
            job = JobCard.search(domain, limit=1, order="id desc")
        except Exception as err:  # noqa: BLE001
            _logger.warning("Gate Pass: job card lookup on %s failed (%s)", model_name, err)
            return False
        if not job:
            return False
        self.job_card_model = model_name
        self.job_card_id = job.id
        self.job_card_no = job.display_name
        for candidate in ("stage_id", "cc_stage_id", "state", "status"):
            if candidate in job_fields and job[candidate]:
                value = job[candidate]
                self.job_card_status = (
                    value.display_name if isinstance(value, models.BaseModel) else str(value)
                )
                break
        return True

    def _sync_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return True
        if not self.customer_id:
            return False
        invoice = self.env["account.move"].search(
            [
                ("move_type", "=", "out_invoice"),
                ("partner_id", "=", self.customer_id.id),
                ("state", "!=", "cancel"),
            ],
            limit=1,
            order="id desc",
        )
        if invoice:
            self.invoice_id = invoice.id
            return True
        return False

    def action_sync_links(self):
        """Refresh every external link without changing the workflow state."""
        for record in self:
            record._auto_link_booking()
            record._sync_quotation()
            record._sync_rfq()
            record._sync_job_card()
            record._sync_invoice()
        return self._notify(
            _("Links refreshed"),
            _("Booking, quotation, RFQ, job card and invoice links were re-checked."),
            "success",
        )

    def action_open_reference(self, field="quotation"):
        """Open the linked quotation / RFQ / job card / booking record."""
        self.ensure_one()
        mapping = {
            "quotation": (self.quotation_model, self.quotation_id),
            "rfq": (self.rfq_model, self.rfq_id),
            "job_card": (self.job_card_model, self.job_card_id),
            "booking": (self.booking_model, self.booking_id),
        }
        model_name, res_id = mapping.get(field, (False, False))
        if not model_name or not res_id or model_name not in self.env:
            raise UserError(_("There is no linked record to open yet."))
        return {
            "type": "ir.actions.act_window",
            "res_model": model_name,
            "res_id": res_id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice is linked to this gate pass."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ==================================================================
    # Signature
    # ==================================================================
    def save_signature(self, signature, signed_by=None):
        self.ensure_one()
        if not signature:
            raise UserError(_("The signature is empty."))
        self.write({
            "signature": signature,
            "signed_by": signed_by or (self.customer_id.name or ""),
            "signed_at": fields.Datetime.now(),
        })
        return True

    def clear_signature(self):
        self.ensure_one()
        self.write({"signature": False, "signed_by": False, "signed_at": False})
        return True

    # ==================================================================
    # Helpers
    # ==================================================================
    def _notify(self, title, message, kind="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": kind,
                "sticky": False,
            },
        }

    def action_jobs_list(self):
        return {
            'name': ('Jobs'),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'context': {},
            'domain': [('vehicle_id', '=', self.vehicle_id.id), ('is_jobcard', '=', True)],
            'target': 'current',
            'type': 'ir.actions.act_window',
        }

    def action_vehicle_inspection_list(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
        'vehicle_inspection_report.action_vehicle_inspection')
        # inspection_form = self.env.ref('vehicle_inspection_report.view_form_v_job_card_extension', False)
        # inspection_tree = self.env.ref('vehicle_inspection_report.view_tree_v_job_card_extension', False)
        requested_services = []
        if self.requested_services_ids:
            for service in self.requested_services_ids:
                requested_services.append({
                    'product_id': service.product_id.id,
                    'assign_hours': service.assign_hours,
                    'remark': service.remark,       
                })
        print("requested_services,,,,,,,,,,", requested_services)
        action['domain'] = [('vehicle_id', '=', self.vehicle_id.id), ('is_vc', '=', True)]
        ctx = dict(self.env.context)
        ctx.update({
            'default_is_vc': True,
            'default_gate_pass_id': self.id,
            'default_vehicle_id': self.vehicle_id.id,
            'default_repair_category_id': self.repair_category_id.id,
            'default_repair_sub_category_ids': [(6, 0, self.repair_sub_category_ids.ids)],
            'default_requested_services_ids': requested_services,
        })
        action['context'] = ctx
        return action

    def action_sales_list(self):
        return {
            'name': ('Sale order'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'context': {},
            'domain': [('vehicle_id', '=', self.vehicle_id.id)],
            'target': 'current',
            'type': 'ir.actions.act_window',
        }

    def action_invoices_list(self):
        return {
            'name': ('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'context': {'default_move_type': 'out_invoice'},
            'domain': [('vehicle_id', '=', self.vehicle_id.id)],
            'target': 'current',
            'type': 'ir.actions.act_window'
        }

class JobRequestedService(models.Model):
    _inherit = 'job.requested.service'

    gate_pass_id = fields.Many2one('odex.gate.pass', string="GatePass")
