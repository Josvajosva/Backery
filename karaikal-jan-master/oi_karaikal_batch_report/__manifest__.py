# -*- coding: utf-8 -*-

{
    'name': 'Batch Transfer Report',
    'version': '1.2',
    'category': 'Inventory/Inventory',
    'description': """
This module adds the batch transfer  report option 
    """,
    'depends': ['stock','stock_picking_batch','mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_inherit.xml',
        'views/stock_picking_batch_inherit.xml',
        'report/report_batch_action.xml',
        'report/report_batch_template.xml',
        'report/lot_serial_lable.xml',
        'data/ir_cron_inherit.xml'

    ],
    'installable': True,
    'license': 'LGPL-3',
    
}
