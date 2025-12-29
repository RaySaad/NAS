# -*- coding: utf-8 -*-
{
    'name': 'Contact Extension',
    'version': '1.0',
    'category': 'Contacts',

    'depends': ['base','mail','base_setup','contacts', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/contact_views.xml',
    ],
    
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
