# -*- coding: utf-8 -*-
{
    'name': 'Booking',
    'summary': 'Odex Workshop Booking - Online Appointment Scheduling',
    'description': """
Standalone workshop appointment scheduling for Odex Workshop Management System.
Public website booking wizard, customer portal, internal booking app with
dashboard, slot management, calendar integration, rescheduling and reports.
Integrates with Contacts (res.partner), Fleet (fleet.vehicle) and Calendar.
No CRM / Job Card / Sales / Invoicing integration by design.
    """,
    'version': '18.0.3.0.0',
    'category': 'Services/Booking',
    'author': 'ODEX',
    'website': 'https://odex.in',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'fleet',
        'calendar',
        'website',
        'portal',
        # Required by the customer portal: the quotation page reuses Odoo's
        # own sale portal implementation (route, access token, Accept & Sign,
        # message thread) instead of reimplementing it, and Service History /
        # Invoices read account.move, which `sale` pulls in.
        'sale',
    ],
    'data': [
        'security/booking_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/service_type_data.xml',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        'views/booking_views.xml',
        'views/slot_views.xml',
        'views/schedule_views.xml',
        'views/reschedule_views.xml',
        'views/config_views.xml',
        'views/fleet_partner_views.xml',
        'views/menus.xml',
        'views/website_templates.xml',
        'views/portal_templates.xml',
        'views/portal_workshop_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_workshop_booking/static/src/dashboard/**/*',
            'odex_workshop_booking/static/src/backend/schedule.scss',
        ],
        'web.assets_frontend': [
            'odex_workshop_booking/static/src/website/booking_wizard.scss',
            'odex_workshop_booking/static/src/website/booking_wizard.js',
            'odex_workshop_booking/static/src/website/portal_booking.js',
            'odex_workshop_booking/static/src/website/portal_workshop.scss',
        ],
    },
    'application': True,
    'installable': True,
}
