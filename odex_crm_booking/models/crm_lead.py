from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# CRM display field -> (short key, fleet.vehicle candidates, most specific first)
VEHICLE_INFO = {
    "odex_license_plate": ("plate", ["license_plate", "registration_no", "plate_no"]),
    "odex_vehicle_make": ("make", ["vehicle_make_id", "brand_id", "make_id"]),
    "odex_vehicle_model": ("model", ["model_id", "vehicle_model_id"]),
    "odex_chassis_no": ("chassis", ["vin_sn", "chassis_no", "chassis_number", "vin"]),
    "odex_cylinder_count": ("cylinder", ["cylinder_count", "cylinders", "no_of_cylinders",
                                         "cylinder", "x_odex_cylinder_count"]),
    "odex_vehicle_colour": ("colour", ["color_id", "colour_id", "vehicle_color_id", "color", "colour"]),
    "odex_engine_no": ("engine", ["engine_no", "engine_number", "engine_num", "x_odex_engine_no"]),
    "odex_vehicle_year": ("year", ["manufacturing_year", "year", "model_year", "year_of_manufacture"]),
}
WRITABLE_TYPES = ("char", "text", "integer", "float")


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ---- customer details ------------------------------------------------
    alternate_phone = fields.Char("Alternate Number")
    customer_waiting = fields.Boolean("Customer Waiting", tracking=True)
    extra_info = fields.Text("Extra Info")
    odex_business_id = fields.Many2one("odex.crm.business", "Business", tracking=True)
    odex_customer_type_id = fields.Many2one("odex.crm.customer.type", "Customer Type", tracking=True)

    # ---- vehicle ---------------------------------------------------------
    vehicle_id = fields.Many2one("fleet.vehicle", "Vehicle", tracking=True, index=True)
    odometer_reading = fields.Float("Odometer Reading (KM)", digits=(16, 0), tracking=True)
    odex_vehicle_partner_id = fields.Many2one(
        "res.partner", compute="_compute_odex_vehicle_partner")
    odex_allowed_vehicle_ids = fields.Many2many(
        "fleet.vehicle", compute="_compute_odex_allowed_vehicles")
    odex_vehicle_ro = fields.Char(compute="_compute_odex_vehicle_meta")
    odex_vehicle_last_odometer = fields.Float(
        "Last Recorded Odometer", digits=(16, 0), compute="_compute_odex_vehicle_meta")

    # displayed from fleet.vehicle - nothing is stored on the lead
    odex_license_plate = fields.Char("License Plate", compute="_compute_vehicle_info",
                                     inverse="_inverse_vehicle_info")
    odex_vehicle_make = fields.Char("Vehicle Make", compute="_compute_vehicle_info",
                                    inverse="_inverse_vehicle_info")
    odex_vehicle_model = fields.Char("Model", compute="_compute_vehicle_info",
                                     inverse="_inverse_vehicle_info")
    odex_chassis_no = fields.Char("Chassis No.", compute="_compute_vehicle_info",
                                  inverse="_inverse_vehicle_info")
    odex_cylinder_count = fields.Char("Cylinder Count", compute="_compute_vehicle_info",
                                      inverse="_inverse_vehicle_info")
    odex_vehicle_colour = fields.Char("Colour", compute="_compute_vehicle_info",
                                      inverse="_inverse_vehicle_info")
    odex_engine_no = fields.Char("Engine No.", compute="_compute_vehicle_info",
                                 inverse="_inverse_vehicle_info")
    odex_vehicle_year = fields.Char("Year", compute="_compute_vehicle_info",
                                    inverse="_inverse_vehicle_info")

    # ---- smart buttons ---------------------------------------------------
    booking_count = fields.Integer("Bookings", compute="_compute_booking_count")
    odex_activity_count = fields.Integer("Activity Count", compute="_compute_odex_activity_count")

    # ------------------------------------------------------------- helpers
    def _bridge(self):
        return self.env["odex.crm.booking.bridge"]

    @api.model
    def _odex_vehicle_field(self, candidates):
        flds = self.env["fleet.vehicle"]._fields
        return next((c for c in candidates if c in flds), False)

    def _odex_vehicle_owner(self, vehicle):
        owner = self._bridge()._vehicle_owner_field()
        return (vehicle.sudo()[owner] if owner and vehicle else self.env["res.partner"]), owner

    @staticmethod
    def _odex_belongs(owner, partner):
        """Owner unset -> free vehicle. Otherwise same commercial entity."""
        if not owner or not partner:
            return True
        return owner.commercial_partner_id == partner.commercial_partner_id

    # ------------------------------------------------------------ computes
    @api.depends("partner_id")
    def _compute_odex_vehicle_partner(self):
        for lead in self:
            lead.odex_vehicle_partner_id = lead.partner_id.commercial_partner_id

    @api.depends("partner_id")
    def _compute_odex_allowed_vehicles(self):
        owner = self._bridge()._vehicle_owner_field()
        Vehicle = self.env["fleet.vehicle"]
        for lead in self:
            commercial = lead.partner_id.commercial_partner_id
            if owner and commercial:
                lead.odex_allowed_vehicle_ids = Vehicle.search(
                    [(owner, "child_of", commercial.id)], limit=500)
            else:
                lead.odex_allowed_vehicle_ids = Vehicle

    @api.depends("vehicle_id")
    def _compute_odex_vehicle_meta(self):
        """odex_vehicle_ro lists the keys the form must keep read-only: relational
        master data (make, model, colour m2o...) or fields missing on fleet.vehicle."""
        flds = self.env["fleet.vehicle"]._fields
        readonly = ",".join(
            key for crm, (key, cands) in VEHICLE_INFO.items()
            if not self._odex_vehicle_field(cands)
            or flds[self._odex_vehicle_field(cands)].type not in WRITABLE_TYPES)
        for lead in self:
            lead.odex_vehicle_ro = ",%s," % readonly
            lead.odex_vehicle_last_odometer = lead.vehicle_id.sudo().odometer if lead.vehicle_id else 0.0

    @api.depends("vehicle_id")
    def _compute_vehicle_info(self):
        resolved = {crm: self._odex_vehicle_field(c) for crm, (_k, c) in VEHICLE_INFO.items()}
        for lead in self:
            vehicle = lead.vehicle_id.sudo()  # display only; edits go through the inverse
            for crm, fname in resolved.items():
                value = vehicle[fname] if vehicle and fname else False
                if hasattr(value, "_name"):
                    value = value.name if "name" in value._fields else value.display_name
                lead[crm] = str(value) if value not in (False, None, "", 0) else False

    def _inverse_vehicle_info(self):
        flds = self.env["fleet.vehicle"]._fields
        for lead in self.filtered("vehicle_id"):
            vals = {}
            for crm, (_key, cands) in VEHICLE_INFO.items():
                fname = self._odex_vehicle_field(cands)
                if not fname or flds[fname].type not in WRITABLE_TYPES:
                    continue
                raw = lead[crm] or False
                ftype = flds[fname].type
                try:
                    new = (int(float(raw)) if ftype == "integer" else float(raw)) \
                        if ftype in ("integer", "float") and raw else raw
                except ValueError:
                    raise ValidationError(_("%s must be a number.", lead._fields[crm].string))
                if ftype in ("integer", "float"):
                    new = new or 0
                if (lead.vehicle_id[fname] or False) != (new or False):
                    vals[fname] = new
            if vals:
                lead.vehicle_id.write(vals)

    def _compute_booking_count(self):
        counts = self._bridge()._booking_counts(self)
        for lead in self:
            lead.booking_count = counts.get(lead.id, 0)

    @api.depends("activity_ids")
    def _compute_odex_activity_count(self):
        for lead in self:
            lead.odex_activity_count = len(lead.activity_ids)

    # ----------------------------------------------------------- onchanges
    @api.onchange("partner_id")
    def _onchange_partner_odex(self):
        partner = self.partner_id
        if not partner:
            return
        mobile = partner.mobile if "mobile" in partner._fields else False
        if mobile and not self.alternate_phone and mobile != (self.phone or partner.phone):
            self.alternate_phone = mobile
        if not (self.odex_business_id and self.odex_customer_type_id):
            last = self.search([("partner_id", "child_of", partner.commercial_partner_id.id),
                                ("id", "!=", self._origin.id or 0),
                                "|", ("odex_business_id", "!=", False),
                                ("odex_customer_type_id", "!=", False)], order="id desc", limit=1)
            self.odex_business_id = self.odex_business_id or last.odex_business_id
            self.odex_customer_type_id = self.odex_customer_type_id or last.odex_customer_type_id
        warning = None
        if self.vehicle_id:
            owner, _f = self._odex_vehicle_owner(self.vehicle_id)
            if not self._odex_belongs(owner, partner):
                warning = {"title": _("Vehicle cleared"), "message": _(
                    "%(v)s belongs to %(o)s, not to %(p)s. Select one of the customer's vehicles.",
                    v=self.vehicle_id.display_name, o=owner.display_name, p=partner.display_name)}
                self.vehicle_id = False
        if not self.vehicle_id:
            allowed = self.odex_allowed_vehicle_ids
            if len(allowed) == 1:
                self.vehicle_id = allowed
        return {"warning": warning} if warning else None

    @api.onchange("vehicle_id")
    def _onchange_vehicle_odex(self):
        owner, _f = self._odex_vehicle_owner(self.vehicle_id)
        if self.vehicle_id and owner and not self.partner_id:
            self.partner_id = owner

    @api.onchange("odometer_reading")
    def _onchange_odometer_odex(self):
        last = self.odex_vehicle_last_odometer
        if self.vehicle_id and self.odometer_reading and last and self.odometer_reading < last:
            return {"warning": {"title": _("Odometer lower than last reading"), "message": _(
                "The last recorded odometer for this vehicle is %(last)s KM. "
                "Check the reading before saving.", last="{:,.0f}".format(last))}}

    # --------------------------------------------------------- constraints
    @api.constrains("partner_id", "vehicle_id")
    def _check_vehicle_customer(self):
        for lead in self.filtered(lambda r: r.vehicle_id and r.partner_id):
            owner, _f = self._odex_vehicle_owner(lead.vehicle_id)
            if not self._odex_belongs(owner, lead.partner_id):
                raise ValidationError(_(
                    "Vehicle %(v)s belongs to %(o)s, not to the selected customer %(p)s.",
                    v=lead.vehicle_id.display_name, o=owner.display_name,
                    p=lead.partner_id.display_name))

    @api.constrains("vehicle_id", "odometer_reading")
    def _check_odometer_reading(self):
        for lead in self:
            if lead.vehicle_id and lead.odometer_reading <= 0:
                raise ValidationError(_("Odometer Reading (KM) is required once a vehicle is selected."))
            if lead.odometer_reading < 0:
                raise ValidationError(_("Odometer Reading (KM) cannot be negative."))

    # ----------------------------------------------------- vehicle syncing
    def _odex_sync_vehicle(self):
        """Attach a free vehicle to the customer and push the reading to fleet.

        Runs as sudo: fleet driver changes write assignation logs and odometer
        logs that sales users have no rights on; the lead-level checks above
        already validated the data.
        """
        for lead in self.filtered("vehicle_id"):
            vehicle = lead.vehicle_id.sudo()
            owner, owner_field = self._odex_vehicle_owner(vehicle)
            if owner_field and not owner and lead.partner_id:
                vehicle.write({owner_field: lead.partner_id.id})
            if lead.odometer_reading and lead.odometer_reading > (vehicle.odometer or 0):
                vehicle.odometer = lead.odometer_reading  # fleet inverse logs fleet.vehicle.odometer

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._odex_sync_vehicle()
        return leads

    def write(self, vals):
        res = super().write(vals)
        if {"vehicle_id", "partner_id", "odometer_reading"} & set(vals):
            self._odex_sync_vehicle()
        return res

    # ------------------------------------------------------------- actions
    def action_create_booking(self):
        self.ensure_one()
        missing = [label for label, ok in (
            (_("Customer Name"), self.partner_id),
            (_("Contact Number"), self.phone or self.mobile),
            (_("Vehicle"), self.vehicle_id),
            (_("Odometer Reading (KM)"), self.odometer_reading > 0),
        ) if not ok]
        if missing:
            raise UserError(_("Fill these before creating a booking:\n- %s", "\n- ".join(missing)))
        model_name, ctx = self._bridge()._booking_defaults(self)
        # never leak the CRM action's defaults (default_type='opportunity', team...) into the booking
        base_ctx = {k: v for k, v in self.env.context.items()
                    if not k.startswith(("default_", "search_default_"))}
        return {
            "type": "ir.actions.act_window",
            "name": _("New Booking"),
            "res_model": model_name,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": dict(base_ctx, **ctx),
        }

    def action_view_bookings(self):
        self.ensure_one()
        model_name, lead_field = self._bridge()._require()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Bookings"),
            "res_model": model_name,
            "domain": [(lead_field, "=", self.id)],
            "context": {"default_%s" % lead_field: self.id},
        }
        bookings = self.env[model_name].search([(lead_field, "=", self.id)])
        if len(bookings) == 1:
            action.update(view_mode="form", views=[(False, "form")], res_id=bookings.id)
        else:
            action.update(view_mode="list,form", views=[(False, "list"), (False, "form")])
        return action

    def action_view_odex_activities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Activities"),
            "res_model": "mail.activity",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {
                "default_res_model_id": self.env["ir.model"]._get_id(self._name),
                "default_res_id": self.id,
            },
        }
