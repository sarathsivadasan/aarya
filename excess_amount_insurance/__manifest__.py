# Copyright 2021 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Prints Extend",
    "summary": "Prints Extend",
    "version": "18.0.1.0.0",
    "category": "Other",
    "website": "",
    "author": "AB",
    "maintainers": ["AB"],
    "license": "AGPL-3",
    "depends": ["base","purchase", "sale", "account", "account_invoice_fixed_discount",],
    "data": [
        "data/product_data.xml",
        # "report/custom_header_footer.xml",
        # "report/custom_account_move.xml",
        "views/extend_account_move.xml",
        # "report/custom_proforma.xml",

        # "views/res_partner_views.xml"
    ],
    # "assets": {
    #     'web.assets_backend': [
    #         'prints_extend/static/src/scss/style.css',
    #     ],
    # },
    # 'images': ['static/src/images/logo.png'],
}
