# -*- coding: utf-8 -*-
{
    'name': 'Odex Coupon Managements',
    'version': '18.0.2.0.2',
    'category': 'Automotive/Workshop',
    'summary': 'Coupon & Service Package Management for Automotive Workshop',
    'description': """
        Complete Coupon / Service Package Management system for automotive workshops.

        Features:
        - Coupon Master (Coupon Types) with service lines
        - Customer Coupon with vehicle assignment
        - Cash / Bank / PDC payment registration
        - Unearned Revenue accounting on booking
        - Revenue recognition on service invoice
        - Coupon usage tracking & history
        - PDF print report
        - Fleet integration
        - Scheduled expiry check
    """,
    'author': 'Odex Solutions',
    'website': 'https://www.odex.com',
    'depends': [
        'base',
        'mail',
        'account',
        'product',
        'fleet','post_dated_cheque_mgt_app'
    ],
    'data': [
        # Security first
        'security/coupon_security.xml',
        'security/ir.model.access.csv',
        # Sequences & config data
        'data/ir_sequence_data.xml',
        'data/coupon_config_data.xml',
        # Views
        'views/coupon_master_views.xml',
        'views/coupon_payment_views.xml',
        'views/customer_coupon_views.xml',
        'views/coupon_config_settings_views.xml',
        'views/coupon_dashboard_views.xml',
        'views/project_task.xml',
        # Wizard views
        'wizard/coupon_payment_wizard_views.xml',
        # Reports
        'report/report_customer_coupon.xml',
        # Menus (last so all actions already exist)
        'views/coupon_menus.xml',
        # Demo data
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_coupon_management/static/src/css/coupon_style.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
