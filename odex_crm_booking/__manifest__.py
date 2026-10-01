{
    "name": "ODEX CRM Booking",
    "summary": "CRM Lead -> Vehicle -> Workshop Booking connector with vehicle-service lead form",
    "version": "18.0.2.0.0",
    "category": "Sales/CRM",
    "author": "ODEX",
    "license": "LGPL-3",
    "depends": ["crm", "fleet", "sales_team", "mail", "odex_workshop_booking"],
    "data": [
        "security/ir.model.access.csv",
        "data/crm_config_data.xml",
        "views/crm_config_views.xml",
        "views/crm_lead_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odex_crm_booking/static/src/scss/crm_lead_form.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
