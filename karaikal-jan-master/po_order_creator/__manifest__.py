{
    'name': 'Purchase Order Creator',
    'category': 'Purchases',
    'summary': 'Automatically create purchase orders',
    'description': """
        This module automatically creates Purchase Orders
        based on reordering rules.
    """,
    'version': '18.0.1.0.2',
    'author': 'Ciberon',
    'website': '',
    'depends': [
        'purchase',
        'stock',
        'purchase_stock',
        'account',
        'sale',
        'sale_purchase_inter_company_rules',
        'mrp',
        'mrp_account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/scheduler_config.xml',
        'data/ir_config_parameter.xml',
        'views/po_scheduler_config_views.xml',
        'views/product_product.xml',
        'views/stock_picking_views.xml',
        'report/report_invoice_intercompany_qr.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'po_order_creator/static/src/xml/list_view_buttons.xml',
            'po_order_creator/static/src/xml/scan_input_dialog.xml',
            'po_order_creator/static/src/js/scan_input_dialog.js',
            'po_order_creator/static/src/js/list_controller_po_button.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
