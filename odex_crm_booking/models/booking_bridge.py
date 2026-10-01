"""Runtime bridge between crm.lead and the existing workshop Booking model.

Nothing in this file hardcodes the booking model's ``_name``: a wrong guess
(``odex.booking``) already cost a production install once. The model and the
field names are resolved from the live registry, cached in
``ir.config_parameter`` and can be overridden there:

    odex_crm_booking.booking_model        e.g. odex.workshop.booking
    odex_crm_booking.booking_lead_field   m2o crm.lead on the booking model
    odex_crm_booking.vehicle_owner_field  m2o res.partner on fleet.vehicle
"""
import logging

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MODULE = "odex_crm_booking"
P_MODEL = "odex_crm_booking.booking_model"
P_LEAD_FIELD = "odex_crm_booking.booking_lead_field"
P_OWNER_FIELD = "odex_crm_booking.vehicle_owner_field"

BOOKING_MODULE = "odex_workshop_booking"
BOOKING_CANDIDATES = [
    "odex.workshop.booking", "odex.booking.booking", "odex.booking.request",
    "odex.booking.appointment", "workshop.booking", "odex.booking",
]
# odex_workshop_booking also defines these support models - never the booking itself
NON_BOOKING_TOKENS = ("slot", "schedule", "day", "break", "offday", "availability",
                      "config", "setting", "wizard", "line", "report", "dashboard")
LEAD_FIELD_PREFERENCE = ["lead_id", "crm_lead_id", "opportunity_id", "x_odex_crm_lead_id"]
LEGACY_LEAD_COLUMNS = ["lead_id", "crm_lead_id", "opportunity_id"]
MANUAL_LEAD_FIELD = "x_odex_crm_lead_id"

OWNER_CANDIDATES = ["driver_id", "customer_id", "partner_id", "owner_id"]

# fleet.vehicle fields needed by the CRM form; if none of the candidates exist
# a manual x_odex_* field is created on fleet.vehicle (never a new model).
VEHICLE_MANUAL_FIELDS = {
    "cylinder": ("x_odex_cylinder_count", "integer", "Cylinder Count",
                 ["cylinder_count", "cylinders", "no_of_cylinders", "cylinder", "x_odex_cylinder_count"]),
    "engine": ("x_odex_engine_no", "char", "Engine No.",
               ["engine_no", "engine_number", "engine_num", "x_odex_engine_no"]),
}

# booking field candidates for the Create Booking defaults
BOOKING_DEFAULT_MAP = {
    "partner": ["partner_id", "customer_id"],
    "vehicle": ["vehicle_id", "fleet_vehicle_id", "car_id"],
    "phone": ["phone", "mobile", "contact_number", "mobile_no", "customer_phone", "partner_phone"],
    "alt_phone": ["alternate_phone", "alternative_contact", "alternate_number", "alt_phone",
                  "alternate_mobile", "mobile2"],
    "email": ["email", "email_from", "partner_email", "customer_email"],
    "business": ["business_id", "odex_business_id", "business"],
    "ctype": ["customer_type_id", "odex_customer_type_id", "service_type_id", "customer_type", "job_type"],
    "odometer": ["odometer_reading", "odometer", "odometer_km", "mileage", "km_reading"],
    "waiting": ["customer_waiting", "is_customer_waiting", "is_waiting", "waiting"],
    "note": ["customer_note", "note", "notes", "remarks", "description"],
    "plate": ["license_plate", "registration_no", "plate_no", "vehicle_plate"],
    "chassis": ["chassis_no", "vin_sn", "vin", "chassis_number"],
    "company": ["company_id"],
}


class OdexCrmBookingBridge(models.AbstractModel):
    _name = "odex.crm.booking.bridge"
    _description = "ODEX CRM <-> Booking runtime bridge"

    # ------------------------------------------------------------------ utils
    def _param(self, key):
        return self.env["ir.config_parameter"].sudo().get_param(key) or False

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, value or "")

    @api.model
    def _pick_field(self, model_name, candidates, ttypes=None, comodel=None):
        if not model_name or model_name not in self.env:
            return False
        fields_map = self.env[model_name]._fields
        for name in candidates:
            fld = fields_map.get(name)
            if not fld:
                continue
            if ttypes and fld.type not in ttypes:
                continue
            if comodel and getattr(fld, "comodel_name", None) != comodel:
                continue
            return name
        return False

    # ----------------------------------------------------------- resolution
    @api.model
    def _booking_model(self):
        name = self._param(P_MODEL)
        if name and name in self.env:
            return name
        for cand in BOOKING_CANDIDATES:
            if cand in self.env and self._is_booking_like(cand):
                return cand
        return self._detect_booking_from_module()

    @api.model
    def _is_booking_like(self, name):
        model = self.env[name]
        if model._abstract or model._transient:
            return False
        flds = model._fields.values()
        has_partner = any(f.type == "many2one" and f.comodel_name == "res.partner" for f in flds)
        has_vehicle = any(f.type == "many2one" and f.comodel_name == "fleet.vehicle" for f in flds)
        return has_partner and has_vehicle

    @api.model
    def _detect_booking_from_module(self):
        imd = self.env["ir.model.data"].sudo().search(
            [("module", "=", BOOKING_MODULE), ("model", "=", "ir.model")])
        names = self.env["ir.model"].sudo().browse(imd.mapped("res_id")).exists().mapped("model")
        best, best_score = False, 0
        for name in names:
            if name not in self.env:
                continue
            tail = name.split(".")[-1]
            if any(tok in tail for tok in NON_BOOKING_TOKENS):
                continue
            model = self.env[name]
            if model._abstract or model._transient:
                continue
            flds = model._fields
            score = 0
            score += 3 if any(f.type == "many2one" and f.comodel_name == "fleet.vehicle" for f in flds.values()) else 0
            score += 3 if any(f.type == "many2one" and f.comodel_name == "res.partner" for f in flds.values()) else 0
            score += 2 if "booking" in name else 0
            score += 1 if "state" in flds else 0
            score += 1 if any(f.type == "many2one" and f.comodel_name == "odex.booking.slot" for f in flds.values()) else 0
            if score > best_score:
                best, best_score = name, score
        return best if best_score >= 5 else False

    @api.model
    def _booking_lead_field(self, model_name=None):
        model_name = model_name or self._booking_model()
        if not model_name:
            return False
        name = self._param(P_LEAD_FIELD)
        if name and name in self.env[model_name]._fields:
            return name
        picked = self._pick_field(model_name, LEAD_FIELD_PREFERENCE, ("many2one",), "crm.lead")
        if picked:
            return picked
        for fname, fld in self.env[model_name]._fields.items():
            if fld.type == "many2one" and fld.comodel_name == "crm.lead":
                return fname
        return False

    @api.model
    def _vehicle_owner_field(self):
        name = self._param(P_OWNER_FIELD)
        if name and name in self.env["fleet.vehicle"]._fields:
            return name
        return self._pick_field("fleet.vehicle", OWNER_CANDIDATES, ("many2one",), "res.partner")

    # ---------------------------------------------------------------- setup
    @api.model
    def _ensure_xmlid(self, record, name):
        imd = self.env["ir.model.data"].sudo()
        if not imd.search_count([("module", "=", MODULE), ("name", "=", name)]):
            imd.create({"module": MODULE, "name": name, "model": record._name,
                        "res_id": record.id, "noupdate": True})

    @api.model
    def _create_manual_field(self, model_name, fname, ttype, label, relation=None):
        if fname in self.env[model_name]._fields:
            return False
        vals = {
            "name": fname, "model_id": self.env["ir.model"]._get(model_name).id,
            "ttype": ttype, "field_description": label, "state": "manual", "copied": False,
        }
        if relation:
            vals.update(relation=relation, on_delete="set null", index=True)
        field = self.env["ir.model.fields"].sudo().create(vals)
        self._ensure_xmlid(field, "field_%s__%s" % (model_name.replace(".", "_"), fname))
        return True

    @api.model
    def _migrate_legacy_lead_column(self, model_name, target):
        table = self.env[model_name]._table
        cr = self.env.cr
        for col in LEGACY_LEAD_COLUMNS:
            if col == target:
                continue
            cr.execute("""SELECT 1 FROM information_schema.columns
                          WHERE table_name=%s AND column_name=%s""", (table, col))
            if not cr.fetchone():
                continue
            cr.execute(f'''UPDATE "{table}" b SET "{target}" = b."{col}"
                           WHERE b."{target}" IS NULL AND b."{col}" IN (SELECT id FROM crm_lead)''')
            _logger.info("odex_crm_booking: copied %s legacy %s.%s -> %s",
                         cr.rowcount, table, col, target)

    @api.model
    def _booking_form_view_anchor(self, model_name, lead_field):
        View = self.env["ir.ui.view"].sudo()
        view_id = View.default_view(model_name, "form")
        if not view_id:
            return False, False
        arch = self.env[model_name].get_view(view_id, "form")["arch"]
        root = etree.fromstring(arch)
        if root.xpath("//field[@name='%s']" % lead_field):
            return view_id, None  # already visible on the booking form
        partner = self._pick_field(model_name, BOOKING_DEFAULT_MAP["partner"], ("many2one",))
        vehicle = self._pick_field(model_name, BOOKING_DEFAULT_MAP["vehicle"], ("many2one",))
        for fname in (partner, vehicle):
            if fname and root.xpath("//sheet//field[@name='%s']" % fname):
                return view_id, ("//sheet//field[@name='%s']" % fname, "after")
        if root.xpath("//sheet//group"):
            return view_id, ("(//sheet//group)[1]", "inside")
        if root.xpath("//sheet"):
            return view_id, ("//sheet", "inside")
        return view_id, ("//form", "inside")

    @api.model
    def _ensure_booking_form_link(self, model_name, lead_field):
        xmlid = "%s.booking_form_crm_lead_link" % MODULE
        if self.env.ref(xmlid, raise_if_not_found=False):
            return "exists"
        view_id, anchor = self._booking_form_view_anchor(model_name, lead_field)
        if not view_id or anchor is None:
            return "not needed" if view_id else "no form view"
        expr, position = anchor
        field_xml = ('<field name="%s" string="CRM Lead" '
                     'options="{\'no_create\': True}"/>' % lead_field)
        if position == "inside" and expr != "(//sheet//group)[1]":
            field_xml = "<group>%s</group>" % field_xml
        arch = '<data><xpath expr="%s" position="%s">%s</xpath></data>' % (expr, position, field_xml)
        view = self.env["ir.ui.view"].sudo().create({
            "name": "%s.form.odex.crm.lead" % model_name,
            "model": model_name, "inherit_id": view_id, "priority": 99,
            "mode": "extension", "arch": arch,
        })
        self._ensure_xmlid(view, "booking_form_crm_lead_link")
        return "created"

    @api.model
    def _setup_integration(self):
        result = {}
        # fleet.vehicle: only create the fields that do not exist under any name
        for key, (fname, ttype, label, cands) in VEHICLE_MANUAL_FIELDS.items():
            if not self._pick_field("fleet.vehicle", cands):
                self._create_manual_field("fleet.vehicle", fname, ttype, label)
                result["vehicle_%s" % key] = "created %s" % fname
        owner = self._vehicle_owner_field()
        if owner:
            self._set_param(P_OWNER_FIELD, owner)
        result["vehicle_owner_field"] = owner

        model_name = self._booking_model()
        result["booking_model"] = model_name
        if not model_name:
            _logger.warning("odex_crm_booking: no booking model detected in %s", BOOKING_MODULE)
            return result
        self._set_param(P_MODEL, model_name)
        lead_field = self._booking_lead_field(model_name)
        if not lead_field:
            self._create_manual_field(model_name, MANUAL_LEAD_FIELD, "many2one", "CRM Lead", "crm.lead")
            lead_field = MANUAL_LEAD_FIELD
            self._migrate_legacy_lead_column(model_name, lead_field)
        self._set_param(P_LEAD_FIELD, lead_field)
        result["booking_lead_field"] = lead_field
        result["booking_form"] = self._ensure_booking_form_link(model_name, lead_field)
        return result

    @api.model
    def action_setup(self):
        res = self._setup_integration()
        lines = ", ".join("%s: %s" % (k, v or "-") for k, v in res.items())
        ok = bool(res.get("booking_model"))
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Booking Integration") if ok else _("Booking model not found"),
                "message": lines,
                "type": "success" if ok else "warning", "sticky": not ok,
            },
        }

    # ---------------------------------------------------------- lead helpers
    @api.model
    def _require(self):
        model_name = self._booking_model()
        lead_field = model_name and self._booking_lead_field(model_name)
        if not model_name or not lead_field:
            # first use after install / registry reset: try to self-heal once
            self._setup_integration()
            model_name = self._booking_model()
            lead_field = model_name and self._booking_lead_field(model_name)
        if not model_name or not lead_field:
            raise UserError(_(
                "The Booking model could not be detected.\n"
                "Set the system parameter '%(p)s' to the booking model name and run "
                "CRM > Configuration > Booking Integration.", p=P_MODEL))
        return model_name, lead_field

    @api.model
    def _booking_counts(self, leads):
        model_name = self._booking_model()
        lead_field = model_name and self._booking_lead_field(model_name)
        if not model_name or not lead_field or not leads.ids:
            return {}
        try:
            groups = self.env[model_name]._read_group(
                [(lead_field, "in", leads.ids)], [lead_field], ["__count"])
        except Exception:  # noqa: BLE001 - user without booking rights
            return {}
        return {lead.id: count for lead, count in groups}

    @api.model
    def _value_for(self, model_name, fname, lead_value):
        """Convert a CRM value to something the booking field accepts, or None."""
        fld = self.env[model_name]._fields[fname]
        if fld.type == "many2one":
            if lead_value and getattr(lead_value, "_name", None) == fld.comodel_name:
                return lead_value.id
            return None
        if fld.type in ("char", "text", "html"):
            if hasattr(lead_value, "_name"):
                return lead_value.display_name or None
            return lead_value or None
        if fld.type in ("float", "integer", "monetary"):
            return lead_value if isinstance(lead_value, (int, float)) and lead_value else None
        if fld.type == "boolean":
            return bool(lead_value)
        return None  # selections etc.: never guess a key

    @api.model
    def _booking_defaults(self, lead):
        model_name, lead_field = self._require()
        ctx = {"default_%s" % lead_field: lead.id}
        sources = {
            "partner": lead.partner_id,
            "vehicle": lead.vehicle_id,
            "phone": lead.phone or lead.mobile,
            "alt_phone": lead.alternate_phone,
            "email": lead.email_from,
            "business": lead.odex_business_id,
            "ctype": lead.odex_customer_type_id,
            "odometer": lead.odometer_reading,
            "waiting": lead.customer_waiting,
            "note": lead.extra_info,
            "plate": lead.odex_license_plate,
            "chassis": lead.odex_chassis_no,
            "company": lead.company_id,
        }
        used = {lead_field}
        for key, value in sources.items():
            fname = self._pick_field(model_name, BOOKING_DEFAULT_MAP[key])
            if not fname or fname in used:
                continue
            val = self._value_for(model_name, fname, value)
            if val is not None:
                ctx["default_%s" % fname] = val
                used.add(fname)
        return model_name, ctx
