# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'POS Lot Expiry Warning - Validation',
    'version': '18.0.0.2',
    'category': 'Point of Sale',
    'summary': 'POS lot warning pos lot expiry warning pos serial expiry warning pos lot expiry validation point of sale lot warning point of sale lot expiry warning point of sale serial expiry warning point of sale lot expiry validation point of sales lot expiry warning',
    'description': """
        This odoo app show warning to point of sale user while selling product with expired lot or serial number and also warn user if lot/serial number not exist for selected product, User also have option to restrict creating new lot/serial number for product if expired or not exist. 
    """,
    'author': 'BROWSEINFO',
    'website': "https://www.browseinfo.com/demo-request?app=bi_pos_lot_expiration&version=18&edition=Community",
    "price": 4,
    "currency": 'EUR',
    'depends': ['point_of_sale','product_expiry','pos_self_order','stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/point_of_sale.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            "bi_pos_lot_expiration/static/src/js/models.js",
            "bi_pos_lot_expiration/static/src/js/product_screen.js",
            "bi_pos_lot_expiration/static/src/js/Popups/WarningMessagePopup.js",
            "bi_pos_lot_expiration/static/src/js/Popups/NoLotAvailable.js",
            "bi_pos_lot_expiration/static/src/js/Popups/ExpiryDatePopup.js",
            "bi_pos_lot_expiration/static/src/js/models/pos_store.js",
            'bi_pos_lot_expiration/static/src/xml/Popups/ExpiryDatePopup.xml',
            'bi_pos_lot_expiration/static/src/xml/Popups/NoLotAvailable.xml',
            'bi_pos_lot_expiration/static/src/xml/Popups/WarningMessagePopup.xml',

        ],
    },

    "license": "OPL-1",
    "installable": True,
    'auto_install': False,
    'live_test_url': 'https://www.browseinfo.com/demo-request?app=bi_pos_lot_expiration&version=18&edition=Community',
    "images": ['static/description/Banner.gif'],
}
