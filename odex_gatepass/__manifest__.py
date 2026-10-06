# -*- coding: utf-8 -*-
{
    'name': 'ODEX Gate Pass',
    'category': 'Material/Project',
    'version': '18.0.2.2.0',
    'author': 'Sarasoft',
    'company': 'ODEX',
    'maintainer': 'Sarasoft',
    'website': '',
    'summary': 'ODEX Workshop Gate Pass Management - vehicle IN/OUT lifecycle hub',
    'images': [],
    'description': "Workshop Gate Pass Management System",
    'depends': [
        'fleet',
        'sale_management',
        'account',
    ],
    'data': [
        'security/gate_pass_security.xml',
        'security/ir.model.access.csv',
        'data/gate_pass_seq.xml',
        'views/gate_pass_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_gatepass/static/src/form/gate_pass_form.scss',
            'odex_gatepass/static/src/list/gate_pass_list.js',
            'odex_gatepass/static/src/form/gate_pass_form.js',
            'odex_gatepass/static/src/form/gate_pass_form.xml',
        ],
    },
    'demo': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
