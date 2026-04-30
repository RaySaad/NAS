# -*- coding: utf-8 -*-

{
    'name': 'Employee Financial Statement',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Consolidated financial statement for employees from journal entries',
    'description': """
        Employee Financial Statement Module
        ====================================
        This module provides a consolidated financial statement report for employees
        by pulling all journal entry lines where the employee is tagged.
        
        Features:
        - Support for partner-based employee linking
        - Support for custom employee_id field on journal entry lines
        - Screen list view with export options
        - Professional PDF report with company branding
        - Excel export functionality
        - Optional grouping by account
        - Running balance calculation
    """,
    'author': 'Custom Development',
    'website': '',
    'depends': ['account', 'hr', 'account_ext'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/employee_statement_wizard_views.xml',
        'report/employee_statement_report.xml',
        'report/employee_statement_template.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
