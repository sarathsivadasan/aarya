from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ---- customer details ------------------------------------------------
    alternate_phone = fields.Char("Alternate Number")
    # customer_waiting = fields.Boolean("Customer Waiting", tracking=True)
    extra_info = fields.Text("Extra Info")
    # odex_business_id = fields.Many2one("odex.crm.business", "Business", tracking=True)
    # odex_customer_type_id = fields.Many2one("odex.crm.customer.type", "Customer Type", tracking=True)

    # Vehicle Details
    vehicle_id = fields.Many2one("fleet.vehicle", string="License Plate", tracking=True, index=True)
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="vehicle_id.vehicle_make_id",
                                      string="Vehicle Make")
    vehicle_model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Model")
    vehicle_color_id = fields.Many2one("vehicle.color", related="vehicle_id.color_id", string="Color")
    vin = fields.Char(string="Chassis No.", related="vehicle_id.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle_id.engin_no")
    year = fields.Selection(string="Year", related="vehicle_id.model_year")
    odometer_reading = fields.Char(string="Odometer")

    # ---- smart buttons ---------------------------------------------------
    booking_count = fields.Integer("Bookings", compute="_compute_booking_count")
    odex_activity_count = fields.Integer("Activity Count", compute="_compute_odex_activity_count")

    def _compute_booking_count(self):
        self.booking_count = 0
        # counts = self._bridge()._booking_counts(self)
        # for lead in self:
        #     lead.booking_count = counts.get(lead.id, 0)

    @api.depends("activity_ids")
    def _compute_odex_activity_count(self):
        for lead in self:
            lead.odex_activity_count = len(lead.activity_ids)

    @api.onchange("partner_id")
    def _onchange_partner_odex(self):
        partner = self.partner_id
        if not partner:
            return
        mobile = partner.mobile if "mobile" in partner._fields else False
        if mobile and not self.alternate_phone and mobile != (self.phone or partner.phone):
            self.alternate_phone = mobile

    @api.constrains("vehicle_id", "odometer_reading")
    def _check_odometer_reading(self):
        for lead in self:
            if lead.vehicle_id and lead.odometer_reading <= 0:
                raise ValidationError(_("Odometer Reading (KM) is required once a vehicle is selected."))
            if lead.odometer_reading < 0:
                raise ValidationError(_("Odometer Reading (KM) cannot be negative."))

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
        return {
            "type": "ir.actions.act_window",
            "name": _("New Booking"),
            "res_model": "odex.workshop.booking",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {'default_partner_id': self.partner_id,
                        'default_phone': self.phone,
                        'default_vehicle_id': self.vehicle_id.id,
                        'default_vehicle_vin': self.vin,}
        }

    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Bookings"),
            "res_model": "odex.workshop.booking",
            "domain": [('crm_id', "=", self.id)],
        }
        bookings = self.env['odex.workshop.booking'].search([('crm_id', "=", self.id)])
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
