# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gp_ocr_provider = fields.Selection(
        [("none", "Disabled"), ("local", "Local (pytesseract)"), ("api", "External API")],
        string="OCR Provider",
        config_parameter="odex_vehicle_gate_pass.ocr_provider",
        default="none",
    )
    gp_ocr_endpoint = fields.Char(
        string="OCR Endpoint",
        config_parameter="odex_vehicle_gate_pass.ocr_endpoint",
    )
    gp_ocr_api_key = fields.Char(
        string="OCR API Key",
        config_parameter="odex_vehicle_gate_pass.ocr_api_key",
    )
    gp_require_inspection = fields.Boolean(
        string="Require inspection before Gatepass Out",
        config_parameter="odex_vehicle_gate_pass.require_inspection",
        default=True,
    )
    gp_require_payment = fields.Boolean(
        string="Require full payment before Gatepass Out",
        config_parameter="odex_vehicle_gate_pass.require_payment",
        default=False,
    )
    gp_block_major_damage = fields.Boolean(
        string="Block Gatepass Out on unresolved major damage",
        config_parameter="odex_vehicle_gate_pass.block_major_damage",
        default=False,
    )
