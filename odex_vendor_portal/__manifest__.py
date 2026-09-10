# -*- coding: utf-8 -*-
{
    'name': 'ODEX Vendor Portal',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Vendor portal for RFQs, Purchase Orders and Pending Payments',
    'description': """
ODEX Vendor Portal
==================

Adds a **Vendor** portal user type next to the existing Customer portal user.

* ``Portal User Type`` radio (Customer / Vendor) on the user form.
* Vendor users are redirected to ``/my/vendor`` after login instead of the
  customer portal dashboard.
* Vendor dashboard, RFQ list + response form, Purchase Order list, Pending
  Payments list and Recent Activity.
* Server side security: dedicated group + record rules scoped on the
  commercial partner. A vendor can never read another vendor's documents,
  including by direct URL.

The module reuses the standard portal/website header, footer and layout —
nothing in the existing Customer Portal is modified.
""",
    'author': 'ODEX',
    'website': 'https://www.odex.in',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'website',
        'purchase',
        'account',
    ],
    'data': [
        'security/vendor_portal_security.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/purchase_order_views.xml',
        'views/vendor_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'odex_vendor_portal/static/src/scss/vendor_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
