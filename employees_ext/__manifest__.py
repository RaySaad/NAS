{
    'name': 'Employees Extension',
    'version': '1.0',
    'category': 'Human Resources',

    'depends': ['hr', 'base', 'mail', 'base_setup', 'operating_unit'],
    'data': [
        'security/ir.model.access.csv',
        'data/pc_ou_mapping_data.xml',
        'data/naas_ou_cron.xml',
        'views/employee_views.xml',
        'views/employee_section_views.xml',
        'views/res_config.xml',
        'views/pc_ou_mapping_views.xml',
    ],

    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
