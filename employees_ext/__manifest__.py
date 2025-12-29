{
    'name': 'Employees Extension',
    'version': '1.0',
    'category': 'Human Resources',

    'depends': ['hr', 'base','mail','base_setup', 'operating_unit'],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_views.xml',
        'views/employee_section_views.xml',
        'views/res_config.xml',
    ],
    
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
