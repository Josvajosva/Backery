# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Karaikal Invoice',
    'category': 'Customization',
    'description': """
        Invoice Report Customization B2B Report
    """,
    'summary': 'OI Accounting Invoice',
    'version': '1.0',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com/",
    'depends': ['account', 'l10n_in', 'po_order_creator'],
    'data': [
        'data/paper_format.xml',
        'views/invoices_report.xml',
        'views/e_way_bill_report.xml'

    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
