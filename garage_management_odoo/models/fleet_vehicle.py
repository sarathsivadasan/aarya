from odoo import Command, models, fields, api, _
from odoo.addons.fleet.models.fleet_vehicle_model import FUEL_TYPES
from odoo.exceptions import UserError, ValidationError


class VehicleColor(models.Model):
    _name = "vehicle.color"
    _description = "Vehicle Color"

    name = fields.Char(string="Vehicle Color")

class FleetEmirates(models.Model):
    _name = 'fleet.emirates'
    _description = 'Fleet Emirates'

    name = fields.Char(string="Name")

class FleetCharacters(models.Model):
    _name = 'fleet.characters'
    _description = 'Fleet Characters'

    name = fields.Char(string="Name")


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    # @api.depends('brand_id')
    def _compute_display_name(self):
        for record in self:
            name = record.name
            # if record.brand_id.name:
            #     name = f"{record.brand_id.name}/{name}"
            record.display_name = name

    def _get_years(self):
        return [(str(i), i) for i in range(fields.Date.today().year, 1990, -1)]

    default_fuel_type = fields.Selection(FUEL_TYPES, 'Fuel Type', default='gasoline', tracking=True)
    color_id = fields.Many2one('vehicle.color', tracking=True)
    model_year = fields.Selection(selection='_get_years', default=lambda x: str(fields.Date.today().year), tracking=True)

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    def _get_years(self):
        return [(str(i), i) for i in range(fields.Date.today().year, 1990, -1)]

    # insurance_expiry_date = fields.Date("Insurance Expiry Date")
    # insurance_company_id = fields.Many2one('res.partner', string='Insurance Company', auto_join=True, tracking=True,
    #                                        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    # km_in = fields.Char(string="KM In")
    # km_out = fields.Char(string="KM Out")
    # fuel_in = fields.Char(string="Fuel In")
    # fuel_out = fields.Char(string="Fuel Out")
    
    partner_id = fields.Many2one("res.partner", string="Customer")
    partner_phone = fields.Char(string="Phone", related="partner_id.phone", store=True)
    partner_mobile = fields.Char(string="Mobile", related="partner_id.mobile", store=True)
    partner_email = fields.Char(string="Email", related="partner_id.email", store=True)
    engin_no = fields.Char(string="Engine No.")
    fleet_emirate_id = fields.Many2one('fleet.emirates', string="Emirates")
    fleet_code_id = fields.Many2one('fleet.characters', string="Code")
    vehicle_make_id = fields.Many2one("fleet.vehicle.model.brand", related="model_id.brand_id", string="Vehicle Make")
    fuel_type = fields.Selection(FUEL_TYPES, 'Fuel Type', default="gasoline", compute='_compute_model_fields', store=True, readonly=False)
    color_id = fields.Many2one('vehicle.color', help='Color of the vehicle', compute='_compute_model_fields', store=True, readonly=False)
    model_year = fields.Selection(selection='_get_years', string='Model Year', help='Year of the model', compute='_compute_model_fields', store=True, readonly=False, default=lambda x: str(fields.Date.today().year))
    cylinder_count = fields.Integer(string="Cylinder Count")
    
    @api.depends('fleet_emirate_id.name', 'license_plate')
    def _compute_vehicle_name(self):
        for record in self:
            record.name = (record.fleet_emirate_id.name or '') + '/' + str(record.fleet_code_id.name or '') + '/' + str(record.license_plate or _('No Plate'))
            
    @api.constrains('vin_sn')
    def _check_chassis_no(self):
       if self.vin_sn and len(str(self.vin_sn)) != 17:
           raise ValidationError("Chassis No will have no more/less than 17 characters.")


