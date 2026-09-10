# -*- coding: utf-8 -*-
{
    'name': 'Per User Product Price Visibility',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Hide product cost and sales price for selected users',
    'description': """
Per User Product Price Visibility
=================================

Adds a **Hide Cost & Sales Price** checkbox on the user form. When it is ticked
for a user, the cost and the sales price of products are removed from every
product view (list, kanban, form, search) for that user, and blanked out of the
values the server sends back for those fields.

Typical use: a workshop storekeeper who needs the Inventory product catalogue
but must not see purchase cost or selling price.
""",
    'author': 'ODEX',
    'maintainer': 'ODEX',
    'license': 'LGPL-3',
    'depends': ['product'],
    'data': [
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
