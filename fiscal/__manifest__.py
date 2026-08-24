# -*- coding: utf-8 -*-
{
    'name': 'Fiscal',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'Integration of Fiscal periods in your accounting.',
    'description': r"""
        Integration of Fiscal periods in your accounting.""",
    'author': 'Wahab Ali Malik',
    'website': 'https://www.dalba.com.sa',
    'category': 'Custom Development',
    'depends': [
        'account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/server_actions.xml',
        'views/account_move.xml',
        'views/fiscal_year.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
