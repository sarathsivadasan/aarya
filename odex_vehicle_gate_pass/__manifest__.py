# -*- coding: utf-8 -*-
{
    "name": "Vehicle Gate Pass",
    "version": "18.0.1.0.0",
    "category": "Workshop",
    "summary": "Vehicle gate pass with OCR plate/Mulkiya scanning, damage map, photos and workshop timeline",
    "description": """
Vehicle Gate Pass
=================

Controls vehicle entry and exit for a workshop.

Workflow
--------
Gatepass In -> Vehicle -> Inspection -> Quotation -> RFQ -> Jobcard -> Invoice -> Gatepass Out

Features
--------
* Gate pass sequence (GP000001) and QR code.
* Customer data from res.partner, vehicle data from fleet.vehicle.
* OCR scan button beside Registration No. (number plate) and Chassis No. (UAE Mulkiya).
* Pluggable OCR provider: disabled, local (pytesseract) or external HTTP API.
  API keys live in system parameters, never in JavaScript.
* Camera capture with automatic fallback to file upload.
* Photos tab with typed vehicle photos.
* Damage map tab with clickable vehicle diagrams and normalised (percent) marker
  coordinates, so markers stay correct on desktop, tablet and mobile.
* Vehicle condition tab including A/C and electrical checks plus an inspection
  checklist.
* Timeline tab that updates automatically on every workflow move.
* Payment status computed from customer invoices (account.move).
* Quotation, RFQ and Job Card links resolved at runtime, so the module installs
  whether or not Sale, Purchase and Project are present.
""",
    "author": "Odex Cloud Technologies LLC",
    "website": "https://www.odexcloud.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "base_setup",
        "web",
        "mail",
        "fleet",
        "account",
        "job_card_extension",
        "garage_management_odoo",
        "vehicle_inspection_report",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/gate_pass_views.xml",
        "views/vehicle_inspection_view.xml",
        "views/res_config_settings_views.xml",
        "views/gate_pass_templates.xml",
        "views/gate_pass_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odex_vehicle_gate_pass/static/src/scss/gate_pass.scss",
            "odex_vehicle_gate_pass/static/src/js/camera.js",
            "odex_vehicle_gate_pass/static/src/js/ocr.js",
            "odex_vehicle_gate_pass/static/src/js/damage_map.js",
            "odex_vehicle_gate_pass/static/src/js/photos.js",
            "odex_vehicle_gate_pass/static/src/js/gate_pass.js",
            "odex_vehicle_gate_pass/static/src/xml/gate_pass_templates.xml",
        ],
    },
    "images": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
