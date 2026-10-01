from odoo import api, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    # find a vehicle from CRM by plate or chassis as well as by name
    _rec_names_search = ["name", "license_plate", "vin_sn", "driver_id.name"]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_id = self.env.context.get("odex_crm_partner_id")
        if partner_id:
            owner = self.env["odex.crm.booking.bridge"]._vehicle_owner_field()
            if owner and owner in fields_list and not res.get(owner):
                res[owner] = partner_id
        return res

    def create_driver_history(self, vals):
        # Driver history is an audit log; sales users creating/assigning a vehicle
        # from a lead have no rights on fleet.vehicle.assignation.log.
        Log = self.env["fleet.vehicle.assignation.log"]
        if not Log.has_access("create"):
            return super(FleetVehicle, self.sudo()).create_driver_history(vals)
        return super().create_driver_history(vals)
