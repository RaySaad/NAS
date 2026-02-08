{
    'name': 'Journal Entry Print',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Professional PDF print for Journal Entries with company branding',
    'description': """
        Journal Entry Print Module
        ==========================
        Professional PDF voucher/print for Journal Entries with:
        - Company logo and branding
        - Complete journal entry details
        - Debit/Credit line items with running totals
        - Approval signatures section
        - Print button on Journal Entry form
    """,
    'author': 'Custom Development',
    'depends': ['account'],
    'data': [
        'report/journal_entry_report.xml',
        'report/journal_entry_template.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
