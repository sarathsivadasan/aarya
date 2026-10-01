from odoo import api, fields, Command, models, _


class HrExpense(models.Model):
    _inherit = "hr.expense"

    customer_id = fields.Many2one(comodel_name='res.partner', string="Customer Name")
    partner_phone = fields.Char(string="Contact Number", related="customer_id.phone")
    job_id = fields.Many2one('project.task', string="Job Card")
    vehicle_id = fields.Many2one('fleet.vehicle', string="Registration Number")
    vehicle_color = fields.Many2one('vehicle.color', 
        string="Vehicle Colors", related="vehicle_id.color_id")
    brand = fields.Many2one('fleet.vehicle.model.brand', related="vehicle_id.vehicle_make_id", 
        string="Vehicle Make")
    model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Vehicle Model")
    year = fields.Selection(
        string="Vehicle Manufacturing year", related="vehicle_id.model_year"
    )
    vin = fields.Char(
        string="Vehicle Identification Number", related="vehicle_id.vin_sn"
    )
    engine = fields.Char(
        string="Engine No.", related="vehicle_id.engin_no"
    )
    cylinder_count = fields.Integer(string="Cylinder Count", related="vehicle_id.cylinder_count")
