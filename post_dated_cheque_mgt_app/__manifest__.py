# -*- coding: utf-8 -*-

{
    "name" : "Post Dated Cheque Management(PDC) Odoo",
    "author": "Edge Technologies",
    "version" : "18.0",
    "live_test_url":'https://youtu.be/y5G6ehXbIgI',
    "images":["static/description/main_screenshot.png"],
    'summary': 'Post dated cheque PDC cheque bank PDC check customer postdated check postdated cheque post-dated cheque PDC bill of exchange check payment check management PDC check payment cheque PDC account cheque flow account cheque cycle customer check customer cheque',
    "description": """This app help to user apply PDC payment, generate PDC payment entries, generate journal entries with default configured PDC account, also re-generate journal entries with configured PDC account when the done Collect Cheque from PDC payment from customer invoice and vendor bill. filter PDC payments by stages and customers.


post dated cheque management
odoo PDC cheque
odoo PDC check
bank PDC check
postdated check  in customer invoice and vendor bill
postdated cheque PDC
post-dated cheque
bill of exchange post-dated
PDC bill of exchange
check payment
check management
PDC check payment
PDC cheque PDC
bank PDC check PDC
account cheque flow account cheque cycle bank cheque flow bank cheque cycle
account check flow account check cycle bank cheque flow bank check cycle
post-dated check  in customer invoice and vendor bill
post-dated cheque PDC


     """,
    "license" : "OPL-1",
    "depends" : ['base','sale','purchase','sale_management','account'],
    "data": [
        # 'data/account.account.csv',
        'data/account_data.xml',
        'data/mail_template.xml',
        'security/pdc_payment_group.xml',
        'security/ir.model.access.csv',
        'views/res_config_view.xml',
        'report/pdc_payment_template.xml',
        'report/pdc_payment_action.xml',
        'views/invoice_inherit_view.xml',
        'views/pdc_payment_view.xml',
        'wizard/payment_cash_bounced_wiz_views.xml',
        'wizard/payment_cash_cancelled_wiz_views.xml',
        'wizard/payment_cash_deposit_wiz_views.xml',
        'wizard/payment_cash_returned_wiz_views.xml',
        'wizard/payment_collect_cash_wiz_views.xml',
        'wizard/payment_done_wiz_views.xml',
    ],
    "auto_install": False,
    "installable": True,
    "price": 20,
    "currency": 'EUR',
    "category" : "Accounting",
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
