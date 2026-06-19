# -*- coding: utf-8 -*-
{
    'name': "pos_hide_outofstock_product",

    'summary': "Hide products with zero stock in Odoo 18 POS",

    'description': """
POS Hide Out-of-Stock Products for Odoo 18

This module enhances the Point of Sale (POS) interface by:

- Fetching the current stock quantity (qty_available) for all products from the backend.
- Filtering out products that have zero stock when the 'Hide Out-of-Stock Products' setting is enabled in the POS configuration.
- Ensuring the POS product list only displays available products to cashiers, improving usability and reducing errors.
- Includes detailed debug logging for:
    * Total products loaded
    * Products hidden due to zero stock
    * Products after filtering
    * Final products displayed after exclusions

This module works without modifying any core POS files and leverages Odoo 18's reactive product rendering.
    """,

    'author': "Apurva Wanjari",
    'website': "https://apps.odoo.com/apps/modules/browse?search=apurva+wanjari",
    "license": "LGPL-3",
    'category': 'Point Of Sale',
    'version': '0.18',

    'depends': ['base','point_of_sale', 'product', 'stock'],

    'data': [
        'views/res_config_settings.xml',
        'views/product_category.xml',
        
    ],
    
    'assets': {
        'point_of_sale._assets_pos': [
            "pos_hide_outofstock_product/static/src/js/pos_hide_outofstock.js",
        ],
    },
    
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
 
}

