# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# The composite damage-map image already shows every side, so markers are placed
# on the single image; the "view" is kept for compatibility but defaults to "map".
VIEWS = [
    ("map", "Damage Map"),
]

# Damage legend, matching the artwork: code + colour per type.
DAMAGE_TYPES = [
    ("dent", "D - Dent"),
    ("scratch", "S - Scratch"),
    ("scuff", "Sc - Scuff"),
    ("crack", "C - Crack"),
    ("bent", "B - Bent"),
    ("paint", "P - Paint Damage"),
    ("missing", "M - Missing"),
    ("replaced", "R - Replaced"),
]
DAMAGE_CODE = {
    "dent": "D", "scratch": "S", "scuff": "Sc", "crack": "C",
    "bent": "B", "paint": "P", "missing": "M", "replaced": "R",
}
DAMAGE_COLOR = {
    "dent": "#dc2626", "scratch": "#2563eb", "scuff": "#16a34a", "crack": "#f59e0b",
    "bent": "#7c3aed", "paint": "#b45309", "missing": "#eab308", "replaced": "#111827",
}

SEVERITIES = [
    ("none", "No Damage"),
    ("minor", "Minor"),
    ("major", "Major"),
]


class OdexGatePassDamage(models.Model):
    _name = "odex.gate.pass.damage"
    _description = "Gate Pass Damage Marker"
    _order = "id"

    gate_pass_id = fields.Many2one(
        "odex.gate.pass", string="Gate Pass", required=True, ondelete="cascade", index=True
    )
    view = fields.Selection(VIEWS, string="View", default="map", required=True)
    damage_type = fields.Selection(DAMAGE_TYPES, string="Damage Type", default="dent", required=True)
    severity = fields.Selection(SEVERITIES, string="Severity", default="minor", required=True)
    # Normalised coordinates: percent of the image, so markers are correct at any size.
    x_position = fields.Float(string="X (%)", default=50.0)
    y_position = fields.Float(string="Y (%)", default=50.0)
    description = fields.Char(string="Description")
    resolved = fields.Boolean(string="Resolved", default=False)
    photo_id = fields.Many2one("odex.gate.pass.photo", string="Photo")
    created_by = fields.Many2one(
        "res.users", string="Created By", default=lambda self: self.env.user
    )
    created_at = fields.Datetime(string="Created At", default=fields.Datetime.now)
    code = fields.Char(compute="_compute_code")
    color = fields.Char(compute="_compute_code")

    _sql_constraints = [
        ("x_range", "CHECK(x_position >= 0 AND x_position <= 100)",
         "The horizontal position must be between 0 and 100."),
        ("y_range", "CHECK(y_position >= 0 AND y_position <= 100)",
         "The vertical position must be between 0 and 100."),
    ]

    @api.constrains("x_position", "y_position")
    def _check_coordinates(self):
        for record in self:
            if not (0 <= record.x_position <= 100) or not (0 <= record.y_position <= 100):
                raise ValidationError(
                    _("Damage coordinates must be between 0 and 100 (percent).")
                )

    @api.depends("damage_type")
    def _compute_code(self):
        for record in self:
            record.code = DAMAGE_CODE.get(record.damage_type, "?")
            record.color = DAMAGE_COLOR.get(record.damage_type, "#dc2626")

    @api.depends("damage_type", "severity")
    def _compute_display_name(self):
        types = dict(DAMAGE_TYPES)
        severities = dict(SEVERITIES)
        for record in self:
            record.display_name = "%s (%s)" % (
                types.get(record.damage_type, ""),
                severities.get(record.severity, ""),
            )
