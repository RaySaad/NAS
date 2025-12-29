{
    'name': 'Print Journal Entries Report in Odoo',
    'version': '1.0',
    'category': 'Account',
    'license': 'LGPL-3',
    'summary': 'Allow to print pdf report of Journal Entries.',
    'description': """
        Allow to print pdf report of Journal Entries.
        journal entry
        print journal entry 
        journal entries
        print journal entry reports
        account journal entry reports
        journal reports
        account entry reports
""",
    'author': 'AYYAN',
    'depends': ['base','account','web'],
    'data': [
            'report/report_journal_entries.xml',
            'report/report_journal_entries_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
