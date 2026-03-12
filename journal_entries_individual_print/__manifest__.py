# -*- coding: utf-8 -*-
{
    'name': 'Journal Entries - Print Separate PDFs',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add option to print multiple Journal Entries as separate PDFs in a ZIP',
    'depends': ['account', 'bi_print_journal_entries'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/print_separate_pdf_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
