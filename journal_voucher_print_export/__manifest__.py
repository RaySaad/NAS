# -*- coding: utf-8 -*-
{
    'name': 'Journal Voucher Print & Excel Export',
    'version': '18.0.1.0.2',
    'category': 'Accounting',
    'summary': 'Professional PDF print and Excel export for journal entries with smart size detection',
    'description': """
        Journal Voucher Print & Excel Export
        ====================================
        
        Complete solution for journal entry printing and exporting:
        
        Features:
        ---------
        * Professional PDF Printing: Beautiful voucher design with company branding
        * Excel Export: Handle large entries (5000+ lines) with professional formatting
        * Smart Detection: Auto-choose PDF (<1000 lines) or Excel (>1000 lines)
        * Balance Validation: Ensures entries are balanced before export
        * Draft Support: Can export/print draft entries if balanced
        * Visual Warnings: Color-coded status indicators
        * Frozen Headers: Easy navigation in Excel for large datasets
        * Memory Efficient: Chunk processing for massive entries
        * Odoo 18 Compatible: Full support for analytic distribution
        
        Usage:
        ------
        1. Open any journal entry (draft or posted)
        2. Click "Print Voucher" button for PDF output
        3. Click "Export to Excel" for large entries
        4. System validates balance before proceeding
        
        Perfect for:
        ------------
        * Standard journal voucher printing
        * Bulk salary transfers
        * Large payroll entries (5000+ lines)
        * Mass invoice imports
        * Financial reporting and auditing
        
        Changelog:
        ----------
        Version 18.0.1.0.2:
        - Fixed Excel totals formula bug (last row not included in sum)
        - Corrected data_start_row calculation
        
        Version 18.0.1.0.1:
        - Fixed draft entry filename issue in Excel export
        - Improved filename handling for entries without numbers
        
        Version 18.0.1.0.0:
        - Initial unified release
    """,
    'author': 'Fakhraddin A. Sa\'ad',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'web',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'report/journal_entry_reports.xml',
        'report/journal_entry_template.xml',
        'views/account_move_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
