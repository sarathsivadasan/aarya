# -*- coding: utf-8 -*-
{
    'name': 'Stranbys VAT 201 Report',
    'version': '18.0.1.0.0',
    'summary': """Stranbys VAT 201 Report""",
    'email': "sales@stranbys.com",
    'description': "Vat Return Report",
    'category': "Accounting",
    'author': 'Stranbys Info Solutions',
    'company': 'Stranbys Info Solutions',
    'website': "https://www.stranbys.com",
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/vat_return_report_view.xml'
    ],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
    # 'price': '30.0',
    # 'currency': 'USD',
}
