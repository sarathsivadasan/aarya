# -*- coding: utf-8 -*-
{
    'name': 'Group Based Menu Visibility',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Hide selected menus for every user belonging to a security group',
    'description': """
Group Based Menu Visibility
===========================

Adds a **Hidden Menus** configuration on security groups
(*Settings -> Users & Companies -> Groups -> Menu Visibility*).

Every menu selected there is removed from the menu tree of all users that
belong to the group. Hidden menus are cumulative across the groups a user
belongs to, and hiding a parent menu hides its whole branch.

This is a **menu visibility layer only**. It never touches access rights,
``ir.model.access`` records or record rules.
""",
    'author': 'ODEX',
    'maintainer': 'ODEX',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_groups_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
