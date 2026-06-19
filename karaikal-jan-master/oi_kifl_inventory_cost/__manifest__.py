# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Inventory History Cost & Sale Price',
    'category': 'Customization',
    'summary': 'Adds cost and sales price to inventory move history report',
    'description': """
            Adds two computed fields to Inventory > Reporting > Moves History:
            1. Cost = Product Cost * Quantity Done
            2. Sales Price = Product Sale Price * Quantity Done
            Fields are available in list and pivot views as optional fields.
        """,
    'version': '1.0',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com/",
    'depends': ['stock', 'product'],
    'data': [
        'views/stock_quant.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
