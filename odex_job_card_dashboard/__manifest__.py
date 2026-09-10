{
    'name': 'ODEX Job Card Dashboard',
    'version': '18.0.1.2.0',
    'category': 'Services/Workshop',
    'summary': 'Modern OWL command-center dashboard for Job Cards',
    'description': """
ODEX Job Card Dashboard
=======================
A brand-new, fully interactive OWL dashboard for the Workshop Management System.

* Live status cards driven by job.card.stage (colors/icons/order configurable)
* Drill-down on every card and table row
* Bay occupancy covering both job cards and vehicle inspections
* Overdue promise-date tracking and a customer-waiting board
* Auto refresh plus bus push on every relevant job card change
* Read-group based aggregation - scales to 10,000+ job cards
""",
    'author': 'ODEX',
    'website': 'https://odex.in',
    'license': 'LGPL-3',
    # NOTE: remove any dependency below that is not present in your addons path.
    'depends': [
        'web',
        'project',
        'job_card',
        'job_card_extension',
    ],
    'data': [
        'security/dashboard_security.xml',
        'security/ir.model.access.csv',
        'data/dashboard_config_data.xml',
        'views/job_card_stage_views.xml',
        'views/dashboard_config_views.xml',
        'views/dashboard_views.xml',
    ],
    'demo': [
        'demo/dashboard_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_job_card_dashboard/static/src/scss/dashboard.scss',
            'odex_job_card_dashboard/static/src/js/**/*.js',
            'odex_job_card_dashboard/static/src/xml/**/*.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
