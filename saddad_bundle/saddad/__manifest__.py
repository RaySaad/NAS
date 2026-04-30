# -*- coding: utf-8 -*-
{
    'name': 'Saddad Payments',
    'version': '18.0.1.0.0',
    'category': 'Custom Development',
    'summary': 'Comprehensive Saudi Arabia compliance and document management system',
    'description': """
        Saudi Arabia Document & Payment Management System
        
        This module provides comprehensive management for Saudi Arabia-specific business processes including:
        • Document renewal management (Iqama, work permits, family visas)
        • Employee record management with Hijri date conversion
        • Saddad payment services integration
        • Automated document expiry notifications and reporting
        • Multi-company support with configurable workflows
        • Billers and service provider management
        • Loan and advance request processing
        • Automated journal entries and payment processing
    """,
    'author': 'Waseem Abbas/Dalba Group',
    'website': 'https://www.dalba.com.sa',  # Add your website if applicable
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'fleet',
        'hr',
        'product',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/saddad_security.xml',
        'data/email_template.xml',
        'views/document_renewal.xml',
        'views/renewal_document_type.xml',
        'views/product_category_ext.xml',
        'views/document_renew_expense.xml',
        'data/ir_cron_data.xml',
        'data/employee_sync_cron.xml',
        'views/billers.xml',
        'views/company_loan_account_mapping.xml',
        'views/saddad_services.xml',
        'views/default_journal_mapping.xml',
        'views/morror.xml',
        'views/product_template_ext.xml',
        'reports/muqeem_expenses.xml',
        'data/server_actions.xml',
        'wizard/muqeem_expense_line_details.xml',
        'views/employee_record.xml',
        'views/res_company_ext.xml',
        'data/product_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Add any JS or CSS files to be included in the backend
        ],
        'web.assets_frontend': [
            # Add any JS or CSS files to be included in the frontend
        ]
    },
    'installable': True,
    'application': False,
    'auto_install': False
}
