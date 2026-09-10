{
    'name': 'Employee Asset Management',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Assign company assets to employees and keep a full assignment history',
    'description': """
Employee Asset Management
=========================

Adds an **Assets** tab on the Employee form where HR can record every asset
handed over to an employee (laptops, phones, vehicles, tools...).

Features
--------
* Assets tab + smart button on the Employee form
* Asset picked from the existing Product catalogue (no duplicate master data)
* Serial number / barcode field, scanner friendly, unique while assigned
* Assign date, return date, condition note and free notes
* One click "Return Asset" that keeps the historical record
* Validation: the same physical asset cannot be assigned twice at once
* Standalone "Assets" menu with search, filters and group by
* Access rights for HR Officers, HR Administrators and employees
""",
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': ['hr', 'product'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/employee_asset_views.xml',
        'views/hr_employee_views.xml',
        'views/employee_asset_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
