{
    'name': 'Petty Cash Purchase',
    'version': '1.0',
    'category': 'Human Resources/Expenses',

    'depends': ['hr_expense','fleet','account'],
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
