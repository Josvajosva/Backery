# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OI- Karaikal Sale & Purchase',
    'category': 'Customization',
    'description': """
        Inherit the sale.order.line and add the fields & functionality.
        oi_task_id=HT01441
    """,
    'summary': 'Sales and Purchase',
    'version': '1.3',
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com",
    'depends': ['sale_management', 'purchase', 'stock','sale_purchase_inter_company_rules'],
    'data': [
        'views/sale_order_line.xml',
        'views/purchase_order_line.xml',
        'views/hr_employee.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
