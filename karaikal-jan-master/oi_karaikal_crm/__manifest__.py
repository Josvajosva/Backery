# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Karaikal CRM',
    'category': 'Customization',
    'description': """
        Crm Attachment Automatically attach in while creating the New Quotation.
        oi_task_id=HT01439
    """,
    'summary': 'CRM to sales',
    'version': '1.0',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com",
    'depends': ['crm', 'sale_management', 'sale_crm'],
    'data': [
        'views/sale_order.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
