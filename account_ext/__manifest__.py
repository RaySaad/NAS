# -*- coding: utf-8 -*-
{
    'name': 'Account Ext',
    'version': '19.0.1.0.0',
    'category': 'account',
    'author': 'Custom Development',

    'depends': ['account', 'accountant', 'contacts_ext', 'account_operating_unit', 'employees_ext', 'account_accountant',
                'account_reports', 'account_fleet'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account.xml',
        'views/account_move.xml',
        'views/excel_jv_import_wizard_view.xml',
        'wizard/full_employee_statement_wizard_views.xml',
        'views/full_employee_statement_menus.xml',
        'report/full_employee_statement_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_ext/static/src/components/**/*'
        ]
    },
    'external_dependencies': {
        'python': ['openpyxl', 'xlsxwriter'],
    },
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
