# -*- coding: utf-8 -*-
{
    'name': 'Odex Mulkiya Scan',
    'version': '18.0.1.0.0',
    'category': 'Services/Document Intelligence',
    'summary': 'OCR and document intelligence for UAE Mulkiya / Vehicle Registration Cards',
    'description': """
Odex Mulkiya Scan
=================

Standalone document-intelligence application that reads the front and back side of a
UAE Mulkiya (Vehicle Registration Card), extracts the vehicle information using a
pluggable OCR provider, normalizes it (Arabic + English), matches it against Odoo
master data when available and exposes a clean structured result to any other
application.

This module has **no dependency on Fleet**. Fleet is only the first consumer of the
result and is handled by the separate `odex_mulkiya_scan_fleet` integration module.
    """,
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    # pytesseract is only needed for the local Tesseract provider and is
    # checked at runtime, so it is deliberately not a hard dependency.
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/mulkiya_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mulkiya_match_rule_data.xml',
        'data/mulkiya_alias_data.xml',
        'views/mulkiya_scan_views.xml',
        'views/mulkiya_match_rule_views.xml',
        'views/mulkiya_alias_views.xml',
        'views/res_config_settings_views.xml',
        'views/mulkiya_dashboard_views.xml',
        'views/mulkiya_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_mulkiya_scan/static/src/scss/mulkiya.scss',
            'odex_mulkiya_scan/static/src/js/mulkiya_image_field.js',
            'odex_mulkiya_scan/static/src/js/mulkiya_confidence_field.js',
            'odex_mulkiya_scan/static/src/js/mulkiya_dashboard.js',
            'odex_mulkiya_scan/static/src/xml/mulkiya_image_field.xml',
            'odex_mulkiya_scan/static/src/xml/mulkiya_confidence_field.xml',
            'odex_mulkiya_scan/static/src/xml/mulkiya_dashboard.xml',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}
