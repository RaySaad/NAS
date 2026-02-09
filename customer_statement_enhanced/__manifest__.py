# -*- coding: utf-8 -*-
{
    'name': 'Customer Statement Report Enhanced',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Enhanced Customer Statement Report with Professional Design',
    'description': """
        Professional Customer Statement Report
        ======================================
        * Modern, clean design with gradient header
        * Company branding with logo
        * Clear layout with better readability
        * Color-coded debits and credits
        * Running balance calculation
        * Aging analysis (0-30, 31-60, 61-90, 90+ days)
        * Summary boxes for quick overview
        * Professional table formatting
        * VAT and customer details
        * Print from partner form view
    """,
    'author': 'Ray',
    'website': 'https://www.yourcompany.com',
    'depends': ['account'],
    'data': [
        'report/customer_statement_report.xml',
        'report/customer_statement_template.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
