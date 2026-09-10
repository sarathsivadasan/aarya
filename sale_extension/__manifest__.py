# -*- coding: utf-8 -*-

{
    'name': 'Sale Extension',
    'category': 'sale',
    'version': '18.0.1.0.1',
    'author': 'Odex',
    'company': '',
    'maintainer': 'Odex',
    'website': '',
    'summary': 'Sale Extension',
    'images': [],
    'description': "Sale Extension",
    'depends': ['project', 'base', 'account', 'sale', 'sale_project', 
              'garage_management_odoo', 'job_card_extension', 'portal_quotation_customize'],
    'data': [
        'views/sale_order_views.xml',
        'views/job_card.xml',
        'views/fleet_views.xml',
        'views/sale_estimate_report_view.xml',
    ],
    'demo': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
