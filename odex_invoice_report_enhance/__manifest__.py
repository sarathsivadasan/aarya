# -*- coding: utf-8 -*-
{
    'name': 'Invoice Report Enhance',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Professional automotive workshop Tax Invoice layout '
               '(QWeb inheritance of the standard invoice report).',
    'description': """
Invoice Report Enhance
======================

Enhances the *standard* Odoo invoice PDF/HTML report for the ODEX Workshop
Management System without replacing it.

Key points
----------
* Inherits ``account.report_invoice_document`` using QWeb / XPath only.
* Keeps the standard Odoo header (curved layout, logo, TRN) and footer.
* Redesigns the body to match the workshop quotation layout:
  invoice info row, Customer & Vehicle cards, separate Parts / Labour tables,
  totals summary, amount in words, customer acknowledgement and a dynamic
  QR code that links to the customer portal invoice page.
* Fully upgrade-safe: no core files touched, no report duplicated.
* Multi-company and multi-language aware.
""",
    'author': 'ODEX',
    'website': 'https://www.odex.ae',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'report/invoice_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
