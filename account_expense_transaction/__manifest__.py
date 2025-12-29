# -*- coding: utf-8 -*-
{
    'name': 'Account Expense Transaction',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'All foundational developments for the Account Expense Transaction.',
    'description': r"""
        This module focuses on adding features of the Account Expense Transaction.""",
    'author': 'Wahab Ali Malik',
    'website': 'https://www.dalba.com.sa',
    'category': 'Custom Development',
    'depends': ['account', 'hr','account_operating_unit'],
    'data': [
        "security/security_view.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/account_expense_type_view.xml",
        "views/account_expense_transaction_view.xml",
        "views/product_view.xml",
        "views/invoice_view.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
