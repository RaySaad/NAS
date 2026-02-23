# -*- coding: utf-8 -*-
{
    'name': 'Employee Extension For Saddad',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'All foundational developments within the Employee Model.',
    'description': r"""
        This module focuses on enhancing the overall features of the Employee Model, incorporating all generic improvements.    """,
    'author': 'Waseem Abbas',
    'website': 'https://www.dalba.com.sa',
    'category': 'Custom Development',
    'depends': [
        'base', 'hr', 'hr_payroll'
    ],
    'data': [
        'data/ir_sequence.xml',
        'security/ir.model.access.csv',
        'views/hr_sponsors.xml',
        'views/hr_employee.xml',
    ],
    'installable': False,
    'application': True,
    'auto_install': False,
}
