# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Salary Attachments Customization',
    'version': '1.0',
    'summary': 'Advanced salary attachment and loan management system',
    'description': """
        Enhanced Salary Attachments & Loan Management
        
        This module extends Odoo's HR Payroll capabilities with comprehensive loan and salary attachment management:
        • Employee loan request workflow with multi-level approvals
        • Installment-based payment tracking and management
        • Automated payslip integration with salary deductions
        • Flexible payment methods (direct payment or journal entries)
        • Pardon and postponement request handling
        • Loan merging and consolidation features
        • Comprehensive reporting and payment tracking
        • Multi-company support with role-based access control
    """,
    'author': "Waseem Abbas || Dalba",
    'depends': ['hr_payroll','account'],
    'data': [
        'security/ir.model.access.csv',
        'security/salary_attachment_security.xml',
        'data/server_actions.xml',
        'data/input_types.xml',
        'data/mail_template_data.xml',
        'data/groups.xml',
        'wizard/pardon_request.xml',
        'wizard/postpone_request.xml',
        'views/hr_salary_attachment_ext.xml',
        'views/salary_attachment_type.xml',
        'views/hr_salary_attachment_request.xml',
        'views/hr_salary_attachment_line.xml',
        'views/hr_payslip_views_ext.xml',
        'wizard/merge_attachment.xml',
        # 'views/hr_payslip_batch.xml',
        'views/account_payment_ext.xml',
        'reports/template.xml',
        'reports/report_action.xml'
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
