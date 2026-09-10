# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': 'Auto-Account Setup',
    'version': '18.0.0.1',
    'summary': """Auto-Account Setup""",
    'images': ['static/description/img1.jpeg'],
    'category': 'Inventory/Inventory',
    'depends': [
                'base',
                'account',
                ],
    'data':[
        'security/ir.model.access.csv',
        'views/auto_account_setup.xml',
        # 'views/new_payment.xml',
    ],
    'installable' : True,
    'application' : False,
}

