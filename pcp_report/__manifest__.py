{
    'name': 'Petty Cash Purchase Report in Odoo',
    'version': '1.0',
    'category': 'Account',
    'license': 'LGPL-3',
    'summary': 'Allow to print pdf report of Petty Cash Purchase.',
    'description': """
        Allow to print pdf report of Petty Cash Purchase.
    """,
    'author': 'AYYAN',
    'depends': ['petty_cash_purchases','account','web','base'],
    'data': [
            'report/pcp_temp.xml',
            'report/pcp_temp_report.xml',
    ],
    'installable': True,
    'auto_install': False,
}
