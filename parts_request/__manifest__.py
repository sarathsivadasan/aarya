# -*- coding: utf-8 -*-

{
    'name': 'Parts Request',
    'category': 'Material/Project',
    'version': '18.0.1.0.1',
    'author': 'Sarasoft',
    'company': '',
    'maintainer': 'Sarasoft',
    'website': '',
    'summary': 'You can request parts from Job card',
    'images': [],
    'description': "Parts Request",
    'depends': ['stock', 'hr', 'fleet', 'job_card_extension'],
    'data': [
        'security/ir.model.access.csv',
        'data/part_requisition_seq.xml',
        'views/stock_picking.xml',
        'views/job_card_view.xml',
        'views/purchase_order_view.xml',
        'views/part_requisition_view.xml',
    ],

    'demo': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
