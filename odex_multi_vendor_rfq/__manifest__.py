# -*- coding: utf-8 -*-
{
    'name': 'Odex Multi Vendor RFQ',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Send RFQ to multiple vendors simultaneously and compare quotations',
    'description': """
        Odex Multi Vendor RFQ — Odoo 18 Community
        ==========================================
        * Create one RFQ with multiple products
        * Send to multiple vendors simultaneously
        * Vendor portal submission (no backend login required)
        * Quotation comparison matrix with colour-coded pricing
        * Award complete RFQ or line-wise to different vendors
        * Dashboard statistics and PDF report
        * Full chatter integration
    """,
    'author': 'Odex',
    'website': 'https://odex.in',
    'depends': [
        'purchase',
        'portal',
        'mail',
        'account',
        'garage_management_odoo',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/mail_template_data.xml',
        'wizard/award_rfq_wizard_views.xml',
        'views/purchase_multi_rfq_views.xml',
        'views/purchase_multi_rfq_line_views.xml',
        'views/purchase_order_views_inherit.xml',
        'views/portal_templates.xml',
        'views/menu_views.xml',
        'report/report_multi_rfq_comparison.xml',
        'report/report_templates.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_multi_vendor_rfq/static/src/css/multi_rfq.css',
            'odex_multi_vendor_rfq/static/src/js/multi_rfq.js',
        ],
        'web.assets_frontend': [
            'odex_multi_vendor_rfq/static/src/css/portal_rfq.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
