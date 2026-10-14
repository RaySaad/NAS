{
    'name': 'Petty Cash Purchase',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'author': 'Custom Development',

    'depends': ['hr_expense', 'fleet', 'account', 'account_ext'],
    'data': [
        'data/sequence.xml',
        'security/pcp.xml',
        'security/ir.model.access.csv',
        'views/petty_cash_purchases.xml',
        'views/res_partner.xml',
    ],
    'installable': True,
    'license': 'LGPL-3'
}
