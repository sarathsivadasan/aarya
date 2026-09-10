# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Financial Report',

    'summary': 'Dynamic Financial Report,Profit and loss Report,Balance Sheet Report,Executive,Cash and Flow Report Summary Report,General Ledger Report,Consolidate Journal Report,Age Receivable Report,Age Payable Report,Trial Balance Report,Tax Report',

    'description': """
"
    odoo accounting reports,
    odoo financial reports,
    odoo dynamic financial report,
    odoo dynamic accounting reports,
    odoo balance sheet app,
    create a custom financial report odoo,
    new financial report odoo,
    odoo community financial report,
    odoo community accounting reports,
    odoo Dynamic Reports,
    financial report in odoo,
    odoo financial report builder,
    dynamic financial report in odoo,
    odoo 17 dynamic financial reports,
    odoo custom financial report,
    odoo financial reports in Excel,
    odoo financial reports pdf,
    odoo 17 dynamic financial reports,
    Print odoo dynamic financial reports,
    """,
    'author': 'Ksolves India Ltd.',

    'website': 'https://store.ksolves.com/',

    'live_test_url': 'https://dfr18.kappso.com/web/demo_login',

    'category': 'Accounting/Accounting',

    'currency': 'EUR',

    'version': '18.0.1.0.0',

    'price': '119',

    'license': 'OPL-1',

    'maintainer': 'Ksolves India Ltd.',

    'support': 'sales@ksolves.com',

    'images': ['static/description/DFR2.gif'],

    'depends': ['base', 'mail', 'account', 'sale_management'],

    'auto_install': True,

    'data': ['security/ir.model.access.csv',
             'data/ks_dfr_account_data.xml',
             'data/ks_dynamic_financial_report.xml',
             'security/ks_access_file.xml',
             'views/ks_mail_template.xml',
             'views/ks_searchtemplate.xml',
             'views/ks_base_template.xml',
             'views/ks_dfr_account_type.xml',
             'views/ks_res_config_settings.xml'
             ],

    'assets': {'web.assets_backend': ['ks_dynamic_financial_report/static/src/scss/ks_dynamic_financial_report.scss',
                                      'ks_dynamic_financial_report/static/src/scss/ks_pdf.scss',
                                       '/web/static/lib/jquery/jquery.js',
                                      'ks_dynamic_financial_report/static/src/js/ks_dynamic_action_manager.js',
                                      'ks_dynamic_financial_report/static/src/js/ks_dynamic_financial_report.js',
                                      'ks_dynamic_financial_report/static/src/xml/ks_dynamic_financial_report.xml',
                                      ]},
}
