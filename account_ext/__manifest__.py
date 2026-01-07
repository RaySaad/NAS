# -*- coding: utf-8 -*-
{
    'name': 'Account Ext',
    'version': '1.0',
    'category': 'account',

    'depends': ['accountant', 'contacts_ext', 'account_operating_unit','employees_ext','account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account.xml',
        'views/account_move.xml',
        'views/excel_jv_import_wizard_view.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'account_ext/static/src/components/**/*'
        ]
    },
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
