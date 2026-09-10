# -*- coding: utf-8 -*-
{
    'name': 'Odex Mulkiya Scan - Fleet Integration',
    'version': '18.0.1.0.0',
    'category': 'Services/Document Intelligence',
    'summary': 'Apply Mulkiya OCR results to Fleet vehicles',
    'description': """
Odex Mulkiya Scan - Fleet Integration
=====================================

Integration layer between the standalone Odex Mulkiya Scan application and
Odoo Fleet. It adds:

* a "Scan Mulkiya (OCR)" button on the vehicle form
* a configurable field mapping between the OCR result and fleet.vehicle
* duplicate VIN detection against existing vehicles
* Apply to Vehicle with a full audit trail
* the original Mulkiya images attached to the vehicle

The OCR application itself stays completely independent: uninstalling this
module leaves Odex Mulkiya Scan fully functional.
    """,
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': ['odex_mulkiya_scan', 'fleet'],
    'data': [
        'security/ir.model.access.csv',
        'data/mulkiya_fleet_mapping_data.xml',
        'views/mulkiya_fleet_mapping_views.xml',
        'views/mulkiya_scan_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_mulkiya_scan_fleet/static/src/scss/mulkiya_fleet.scss',
            'odex_mulkiya_scan_fleet/static/src/js/mulkiya_scan_dialog.js',
            'odex_mulkiya_scan_fleet/static/src/js/mulkiya_scan_button.js',
            'odex_mulkiya_scan_fleet/static/src/xml/mulkiya_scan_dialog.xml',
            'odex_mulkiya_scan_fleet/static/src/xml/mulkiya_scan_button.xml',
        ],
    },
    'installable': True,
    'auto_install': True,
}
