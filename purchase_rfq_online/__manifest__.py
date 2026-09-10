{
    "name": "Purchase: Vendor Portal - Sign Purchase RFQ Online",
    "version": "18.0.1.1.0",
    "category": "Purchases",
    "summary": """
    Odoo vendor portal: Send your RFQ to your vendor online,
    they input the price and sign online also
    """,
    "live_test_url": "https://demo18.domiup.com",
    "author": "Domiup (domiup.contact@gmail.com)",
    "price": 65,
    "currency": "EUR",
    "license": "OPL-1",
    "support": "domiup.contact@gmail.com",
    "website": "https://demo18.domiup.com",
    "depends": [
        "purchase",
    ],
    "data": [
        "data/mail_message_subtype_data.xml",
        "views/purchase_order_views.xml",
        "views/purchase_portal_templates.xml",
        "report/purchase_report_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": ["purchase_rfq_online/static/src/js/**/*"],
        "web.assets_tests": [
            "purchase_rfq_online/static/tests/tours/**/*",
        ],
    },
    "test": [],
    "demo": [],
    "images": ["static/description/banner.gif"],
    "installable": True,
    "application": True,
}
