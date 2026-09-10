# -*- coding: utf-8 -*-
{
    'name': 'Petty Cash Book',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Petty Cash Management System - Tally Style Cash Book for Odoo 18 Community',
    'description': """
        Petty Cash Book Module for Odoo 18 Community Edition.
        
        Features:
        - Dashboard with Opening/Closing Balance, Cash Received, Expenses
        - Cash Received (Income) tracking with journal entries
        - Expense (Spending) tracking with journal entries
        - Date range filters (Today, This Week, This Month, etc.)
        - Professional QWeb PDF Reports
        - Accounting integration with journal entries
        - Multi-company support
        - Security groups for User and Manager
    """,
    'author': 'Petty Cash Book',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'mail',
    ],
    'data': [
        # Security
        'security/petty_cash_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequence_data.xml',
        'data/petty_cash_data.xml',
        # Reports
        'report/petty_cash_book_report.xml',
        'report/petty_cash_receipt_voucher_report.xml',
        'report/petty_cash_expense_voucher_report.xml',
        # Wizards
        'wizard/petty_cash_report_wizard_views.xml',
        # Views
        'views/petty_cash_received_views.xml',
        'views/petty_cash_expense_views.xml',
        'views/petty_cash_config_views.xml',
        'views/petty_cash_dashboard_views.xml',
        'views/petty_cash_menus.xml',      
    ],
    'demo': [
        'demo/petty_cash_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'petty_cash_book/static/src/css/petty_cash_dashboard.css',
            'petty_cash_book/static/src/js/petty_cash_dashboard.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
