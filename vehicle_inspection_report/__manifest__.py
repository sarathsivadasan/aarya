

{
    'name': 'Vehicle Inspection Report',
    'version': '1.0',
    'category': 'Fleet',
    'summary': 'Custom Vehicle Inspection Report for Fleet',
    'depends': ['fleet','project', 'job_card', 'job_card_extension'],
    'data': [
        'security/ir.model.access.csv',
        'data/job_card_data.xml',
        'report/vehicle_inspection_report.xml',
        'views/vehicle_inspection_report_template.xml',
        'views/vehicle_view.xml',
        # 'views/fleet_service_log_view.xml',
        'views/sale_order_view.xml',
        'views/fleet_view.xml',
    ],
    'installable': True,
    'application': False,
}