# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Karaikal Product',
    'category': 'Customization',
    'description': """
        Inherit the product.template and add the fields & functionality.
        oi_task_id=HT01440
    """,
    'summary': 'Product Master',
    'version': '1.0',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com/",
    'depends': ['stock','product_expiry'],
    'data': [
        'views/product_template.xml',
        'views/product.xml',
        'data/ir_cron_data_inherit.xml'

    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
