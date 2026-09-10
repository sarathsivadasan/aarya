# -*- coding: utf-8 -*-
{
    'name': 'ODEX Petty Cash',
    'version': '18.0.4.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'ODEX Petty Cash — User-Wise Petty Cash with Full Approval Workflow',
    'description': """
        ODEX Petty Cash Management System v4
        =====================================
        USER-WISE PETTY CASH:
        - Every user has their own petty cash balance
        - Users see only their own transactions
        - Complete received/spent/pending/balance dashboard per user
        - Allocation (Finance → User), Expense, Return workflows
        - Manager approval workflow: Draft→Submitted→Approved/Rejected→Posted
        - Balance = Total Received - Posted Expenses only
        - Pending/Rejected/Draft expenses do NOT reduce balance
        - Over-balance warning on approval
        - Manager dashboard with team balances and pending approvals
        - Full audit trail via chatter
        - Settings-driven GL accounts (no per-transaction GL setup)
        - Expense categories linked to Chart of Accounts
        - QWeb PDF reports
    """,
    'author': 'ODEX',
    'depends': ['account', 'mail', 'analytic', 'hr'],
    'data': [
        'security/odex_petty_cash_security.xml',
        'security/odex_petty_cash_rules.xml',
        'security/ir.model.access.csv',
        'data/odex_petty_cash_data.xml',
        'views/res_config_settings_views.xml',
        'views/odex_petty_cash_account_views.xml',
        'views/odex_petty_cash_allocation_views.xml',
        'views/odex_petty_cash_transaction_views.xml',
        'views/odex_petty_cash_return_views.xml',
        'views/odex_petty_cash_statement_views.xml',
        'views/odex_petty_cash_dashboard_views.xml',
        'views/odex_petty_cash_menus.xml',
        'report/odex_petty_cash_report.xml',
        'report/odex_petty_cash_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_petty_cash/static/src/css/odex_petty_cash.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
