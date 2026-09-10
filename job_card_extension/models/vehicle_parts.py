from odoo import models, fields, api


class VehicleInspectionPart(models.Model):
    _name = "vehicle.inspection.part"
    _description = "Vehicle Inspection Parts"

    inspection_id = fields.Many2one(
        "project.task",
        required=True,
        ondelete="cascade"
    )

    is_confirm = fields.Boolean(string="Is Confirm?", default=True)

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True
    )

    part_no = fields.Char(
        string="Part No",
        related="product_id.barcode",
        store=True,
        readonly=True
    )

    part = fields.Char(string="Parts")

    parts_type = fields.Selection(
        [('original', 'Original'),
         ('duplicate', 'Thijari(Duplicate)'),
         ('used', 'Used'),
         ],
        string='Parts Type',
        default='original',
    )

    quantity = fields.Float(
        default=1.0,
        required=True
    )

    from_inspection = fields.Boolean(string="VNS", readonly="True")
