# -*- coding: utf-8 -*-

from odoo import fields, models, api

FLEET_IMAGES_NAME = [
    ('front_view', 'Front view'),
    ('rear_view', 'Rear view'),
    ('left_side_view', 'Left side view'),
    ('right_side_view', 'Right side view'),
    ('top_view', 'Top view'),
    ('front_left_corner', 'Front-left corner'),
    ('front_right_corner', 'Front-right corner'),
    ('rear_left_corner', 'Rear-left corner'),
    ('rear_right_corner', 'Rear-right corner'),
    ('dent_scratch', 'Any visible dent, scratch, or damage'),
    ('odometer', 'Odometer reading'),
]


class Task(models.Model):
    _inherit = "project.task"

    # register_no = fields.Char(
    #     string="Registration Number"
    # )
    vehicle_id = fields.Many2one('fleet.vehicle',
        string="Registration Number"
    )
    type_id = fields.Many2one(
        'vehicle.type.custom',
        string="Vehicle Type"
    )
    # brand = fields.Char(
    #     string="Vehicle Brand"
    # )
    vehicle_color = fields.Many2one('vehicle.color', 
        string="Vehicle Colors", related="vehicle_id.color_id")
    brand = fields.Many2one('fleet.vehicle.model.brand', related="vehicle_id.vehicle_make_id", 
        string="Vehicle Make")
    # model_name = fields.Char(
    #     string="Model Name"
    # )
    model_id = fields.Many2one("fleet.vehicle.model", related="vehicle_id.model_id", string="Vehicle Model")
    year = fields.Selection(
        string="Vehicle Manufacturing year", related="vehicle_id.model_year"
    )
    vin = fields.Char(
        string="Vehicle Identification Number", related="vehicle_id.vin_sn"
    )
    fuel_type = fields.Selection([
        ('petrol','Petrol'),
        ('diesel','Diesel'),
        ('gas','Gasoline'),
        ('electric', 'Electrical')
    ])
    odometer = fields.Char(
        string="Odometer Reading"
    )
    fuel_level = fields.Char(
        string="Fuel Level"
    )
    engine = fields.Char(
        string="Engine No.", related="vehicle_id.engin_no"
    )
    gear_nos = fields.Char(
        string="No. of Gears"
    )
    repair_category = fields.Many2one(
        'repair.category.custom',
        string="Repair Category"
    )
    detail = fields.Html(
        string="Service Details"
    )
    pay_type = fields.Selection([
        ('free', 'Free'),
        ('paid', 'Paid')
    ], string="Payment Type"
    )
    average_km = fields.Integer(
        string="Average KM/Day"
    )
    is_insurance = fields.Boolean(
        string="Is Insurance Claim"
    )
    insurance_company = fields.Char(
        string="Insurance Company"
    )
    # image1_name = fields.Selection(FLEET_IMAGES_NAME, default="front_view")
    # image2_name = fields.Selection(FLEET_IMAGES_NAME, default="rear_view")
    # image3_name = fields.Selection(FLEET_IMAGES_NAME, default="left_side_view")
    # image4_name = fields.Selection(FLEET_IMAGES_NAME, default="right_side_view")
    # image5_name = fields.Selection(FLEET_IMAGES_NAME, default="top_view")
    # image6_name = fields.Selection(FLEET_IMAGES_NAME, default="front_left_corner")
    # image7_name = fields.Selection(FLEET_IMAGES_NAME, default="front_right_corner")
    # image8_name = fields.Selection(FLEET_IMAGES_NAME, default="rear_left_corner")
    # image9_name = fields.Selection(FLEET_IMAGES_NAME, default="rear_right_corner")
    # image10_name = fields.Selection(FLEET_IMAGES_NAME, default="dent_scratch")
    # image11_name = fields.Selection(FLEET_IMAGES_NAME, default="odometer")
    # image12_name = fields.Selection(FLEET_IMAGES_NAME)
    # image1 = fields.Binary(string="")
    # image2 = fields.Binary(string="")
    # image3 = fields.Binary(string="")
    # image4 = fields.Binary(string="")
    # image5 = fields.Binary(string="")
    # image6 = fields.Binary(string="")
    # image7 = fields.Binary(string="")
    # image8 = fields.Binary(string="")
    # image9 = fields.Binary(string="")
    # image10 = fields.Binary(string="")
    # image11 = fields.Binary(string="")
    # image12 = fields.Binary(string="")
    # image1_desc = fields.Text()
    # image2_desc = fields.Text()
    # image3_desc = fields.Text()
    # image4_desc = fields.Text()
    # image5_desc = fields.Text()
    # image6_desc = fields.Text()
    # image7_desc = fields.Text()
    # image8_desc = fields.Text()
    # image9_desc = fields.Text()
    # image10_desc = fields.Text()
    # image11_desc = fields.Text()
    # image12_desc = fields.Text()

    quality_check_name_ids = fields.One2many(
        'checklist.name.line', 'task_id',
        string="Checklist Names"
    )

    # video_file = fields.Binary(
    #     string="Service Video",
    #     attachment=True
    # )
    # video_filename = fields.Char(
    #     string="Video Filename"
    # )
    # video_description = fields.Text(
    #     string="Video Description"
    # )
    cylinder_count = fields.Integer(string="Cylinder Count", related="vehicle_id.cylinder_count")

    @api.onchange('quality_checklist_id')
    def _onchange_checklist_id(self):
        for rec in self:
            lines=[]
            for checklist in rec.quality_checklist_id:
                checklist_ids = self.mapped('quality_check_name_ids.checklist_id')
                if checklist._origin not in checklist_ids:
                    for name in checklist.checklist_name_ids:
                        lines.append((0,0,{'checklist_name_id':name._origin.id, 'checklist_id':checklist._origin.id, 'task_id': rec.id}))
            rec.quality_check_name_ids = lines

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        for rec in self:
            if rec.vehicle_id and rec.vehicle_id.partner_id:
                rec.partner_id = rec.vehicle_id.partner_id.id