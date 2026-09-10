# -*- coding: utf-8 -*-
{
    'name': 'Bank Reconciliation Pro (Tally Style)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Tally-style bank reconciliation screen for Odoo 18 Community',
    'description': """
        A modern, single-screen bank reconciliation interface inspired by Tally ERP.
        Features:
        - Dashboard summary with opening balance, debits, credits, cleared amount
        - Mismatch detection with red highlight
        - Inline reconciliation with OWL components
        - Multi-select bulk reconciliation
        - Real-time filter and search
        - Right-panel reconciliation form
        - Full accounting integration (account.move.line / account.payment)
    """,
    'author': 'Custom Dev',
    'depends': ['account', 'base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # 'data/demo_data.xml',
        'views/bank_reco_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bank_reconciliation_pro/static/src/css/bank_reco.css',
            'bank_reconciliation_pro/static/src/xml/bank_reco_templates.xml',
            'bank_reconciliation_pro/static/src/js/bank_reco_action.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
