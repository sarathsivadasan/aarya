# -*- coding: utf-8 -*-
{
    'name': 'Odex Garage Technician Portal',
    'version': '18.0.4.0.0',
    'category': 'Services/Field Service',
    'summary': 'Dedicated workspace for garage technicians: inspections, job cards, '
               'parts requests, QC, timers and performance tracking.',
    'description': """
Odex Garage Technician Portal
==============================
A self-contained technician workspace built on top of the existing Odex
garage management stack (project.task, fleet.vehicle, job.cost.sheet,
jobcard.part.requisition, quality.checklist, hr.employee).

Features
--------
* Technician-only dashboard with live counters (Assigned / In Progress /
  Paused / Completed Today / Hours Today)
* Vehicle Inspection workspace (list + detail) with Complaints, Vehicle
  Photos, QC, Parts, Log and Notes tabs
* Server-side timer (Start / Pause / Resume / Complete) immune to browser
  refresh, logout or crash
* Parts Requisition submission straight from the Parts tab
* Technician performance dashboard (today / week / month, efficiency,
  late jobs)
* Technician profile page
* QWeb PDF inspection report with QR code
* Strict record rules: a technician only ever sees their own records
* Administrator view of every assigned job (Job Card or Vehicle
  Inspection) with Pause / Resume / Stop control and a full audit log
* Editable Part information on inspection part lines, kept in step
  between the Vehicle Inspection and the linked Job Card
* macOS / Safari layout corrections, scoped so no other platform is
  affected
    """,
    'author': 'ODEX',
    'website': 'https://odex.ae',
    'license': 'LGPL-3',
    'depends': [
        'project',
        'fleet',
        'mail',
        'hr',
        'stock',
        'product',
        'web',
        'portal',
        'job_card',
        'job_card_extension',
        'garage_management_odoo',
        'vehicle_inspection_report',
        'parts_request',
    ],
    'data': [
        # security
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/technician_record_rules.xml',
        # data
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        # views
        'views/technician_portal_templates.xml',
        'views/technician_portal_menus.xml',
        'views/technician_log_views.xml',
        'views/technician_note_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_employee_kanban_views.xml',
        # report
        'report/inspection_report.xml',
        'report/inspection_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_garage_technician_portal/static/src/css/technician_portal.css',
            # macOS / Safari corrections - every rule inside is scoped
            # under .o_tp_mac / .o_tp_safari, so it cannot match on any
            # other platform. Must load AFTER the base stylesheet.
            'odex_garage_technician_portal/static/src/css/technician_portal_mac.css',
            'odex_garage_technician_portal/static/src/js/platform.js',
            'odex_garage_technician_portal/static/src/js/narrow_screen.js',
            'odex_garage_technician_portal/static/src/js/technician_portal_action.js',
            'odex_garage_technician_portal/static/src/js/components/**/*.js',
            'odex_garage_technician_portal/static/src/xml/**/*.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
