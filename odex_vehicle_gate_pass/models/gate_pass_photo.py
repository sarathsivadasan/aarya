# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

PHOTO_TYPES = [
    ("front", "Front"),
    ("front_right", "Front Right"),
    ("right", "Right Side"),
    ("rear_right", "Rear Right"),
    ("rear", "Rear"),
    ("rear_left", "Rear Left"),
    ("left", "Left Side"),
    ("front_left", "Front Left"),
    ("top", "Top / Roof"),
    ("dashboard", "Dashboard"),
    ("odometer", "Odometer"),
    ("interior", "Interior"),
    ("engine", "Engine Bay"),
    ("tyres", "Tyres"),
    ("damage", "Damage"),
    ("other", "Other"),
]


class OdexGatePassPhoto(models.Model):
    _name = "odex.gate.pass.photo"
    _description = "Gate Pass Photo"
    _order = "taken_at desc, id desc"

    gate_pass_id = fields.Many2one(
        "odex.gate.pass", string="Gate Pass", required=True, ondelete="cascade", index=True
    )
    image = fields.Image(string="Photo", required=True, max_width=1920, max_height=1920)
    image_thumb = fields.Image(
        string="Thumbnail", related="image", max_width=256, max_height=256, store=True
    )
    photo_type = fields.Selection(PHOTO_TYPES, string="Type", default="other", required=True)
    caption = fields.Char(string="Caption")
    taken_at = fields.Datetime(string="Taken At", default=fields.Datetime.now)
    taken_by = fields.Many2one(
        "res.users", string="Taken By", default=lambda self: self.env.user
    )

    def name_get(self):  # kept for older client widgets; harmless on 18
        return [(record.id, record._display()) for record in self]

    @api.depends("photo_type", "caption")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record._display()

    def _display(self):
        label = dict(PHOTO_TYPES).get(self.photo_type, _("Photo"))
        return "%s%s" % (label, " - %s" % self.caption if self.caption else "")
