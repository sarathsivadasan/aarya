# -*- coding: utf-8 -*-

{
    'name': 'Gate Pass',
    'category': 'Material/Project',
    'version': '18.0.1.0.1',
    'author': 'Sarasoft',
    'company': '',
    'maintainer': 'Sarasoft',
    'website': '',
    'summary': 'You can track car in/out position through Gate Pass',
    'images': [],
    'description': "Gate Pass",
    'depends': ['fleet', 'garage_management_odoo'],
    'data': [
        'security/ir.model.access.csv',
        'data/gate_pass_seq.xml',
        'views/job_card.xml',
        'views/gate_pass_view.xml',
    ],

    'demo': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
