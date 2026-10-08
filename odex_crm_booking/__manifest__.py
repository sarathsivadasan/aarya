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
        "views/crm_lead_views.xml",
    ],
    "installable": True,
    "application": False,
}
