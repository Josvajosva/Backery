# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Karaikal Cancel Reason',
    'category': 'stock',
    'description': """Capture the Cancel Reason In delivery & Receipts """,
    'summary': 'Reason Capture',
    'version': '18.0',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com",
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/cancel_reason.xml',
        'views/stock_picking.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
