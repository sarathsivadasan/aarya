# -*- coding: utf-8 -*-
{
    "name": "Odex Technician Overview",
    "version": "18.0.1.0.0",
    "category": "Services/Workshop",
    "summary": "Real-time technician monitoring dashboard and reports for the "
               "Odex Workshop Management System",
    "description": """
Live monitoring dashboard and reporting suite for workshop managers.
Reads all data dynamically from the Odex Garage Technician Portal,
Job Cards, Vehicle Inspections and Timesheets. No duplicated data.
    """,
    "author": "ODEX",
    "website": "https://odex.in",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "hr", "fleet", "hr_timesheet",
                "odex_garage_technician_portal"],
    "data": [
        "security/overview_security.xml",
        "security/ir.model.access.csv",
        "views/actions.xml",
        "views/menu_views.xml",
        "views/schedule_views.xml",
        "report/report_templates.xml",
        "data/cron.xml",
        "data/mail_template.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odex_technician_overview/static/src/scss/overview.scss",
            "odex_technician_overview/static/src/utils/format.js",
            "odex_technician_overview/static/src/dashboard/dashboard.js",
            "odex_technician_overview/static/src/dashboard/dashboard.xml",
            "odex_technician_overview/static/src/reports/reports.js",
            "odex_technician_overview/static/src/reports/reports.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
