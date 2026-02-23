{
    'name': 'Saddad Salary Attachment Connector',
    'version': '18.0.1.0.0',
    'category': 'Custom Development',
    'summary': 'Connector between Saddad and Salary Attachment Requests',
    'license': 'LGPL-3',
    'depends': ['saddad', 'salary_attachments_customization'],
    'data': [
        'views/morror_views.xml',
        'views/salary_attachment_request.xml',
    ],
    'installable': True,
    'auto_install': False,
}