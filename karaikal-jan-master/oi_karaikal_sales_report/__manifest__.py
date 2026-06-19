# -*- coding: utf-8 -*-
{
    'name': 'Sale order Report',
    'version': '1.2',
    'category': 'sale',
    'sequence': 1,
    'summary': 'Sale Order Report',
    'website': 'https://www.odooimplementers.com/',
    'depends': ['base','sale'],
    'data': [
        'reports/sale_order_action.xml',
        'reports/sale_order_view.xml',
         'reports/account_view.xml',
        'reports/account_action.xml',
    ],
    
    'installable': True,
    'auto_install': False,
  
    'license': 'LGPL-3',
}