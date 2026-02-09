# -*- coding: utf-8 -*-
{
    'name': 'Journal Voucher Excel Export',
    'version': '18.0.1.0.1',
    'category': 'Accounting',
    'summary': 'Export large journal entries to Excel with professional formatting',
    'description': """
        Journal Voucher Excel Export
        =============================
        
        Features:
        ---------
        * Smart Print: Automatically uses PDF for small entries (<1000 lines) and Excel for large entries
        * Professional Excel formatting with company branding
        * Handles massive journal entries (5000+ lines) without memory issues
        * Includes balance validation and totals
        * Frozen headers for easy navigation
        * Optimized chunk processing for memory efficiency
        * Odoo 18 compatible with analytic distribution support
        
        Usage:
        ------
        1. Open any posted journal entry
        2. Click "Print Voucher" for auto-detection (PDF or Excel based on size)
        3. Or click "Export to Excel" to force Excel export
        
        Perfect for:
        ------------
        * Bulk salary transfers
        * Large payroll entries
        * Mass invoice imports
        * Any journal entry with 1000+ lines
    """,
    'author': 'Fakhraddin A. Sa\'ad',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'views/account_move_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
