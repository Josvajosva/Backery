# -*- coding: utf-8 -*-
{
    'name': 'eCommerce Pincode Delivery Validation',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Validate delivery availability based on customer shipping pincode during eCommerce checkout and website Sales Orders.',
    'description': """
eCommerce Pincode Delivery Validation
======================================
This module allows you to define Delivery Stores and their deliverable pincodes.

Key Features:
-------------
* **Store Master**: Configure stores with State, City and Main Pincode. State and City are automatically fetched from Contacts/City records.
* **Deliverable Pincodes**: Configure multiple deliverable pincodes per store. Auto-populate city and state from contacts config when entering a pincode.
* **eCommerce Validation**: Customer delivery pincodes are validated during checkout. If non-deliverable, checkout/payment is blocked with a proper warning message.
* **Backend Validation**: Raises validation errors when saving Website Sales Orders with invalid delivery pincodes in the backend.
* **Clean Configuration Menus**: Fully integrated configuration menus under Sales / Configuration / Delivery Stores.
    """,
    'author': 'Antigravity',
    'depends': [
        'sale',
        'website_sale',
        'base_address_extended',
        'auth_signup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_carrier_data.xml',
        'data/website_data.xml',
        'views/delivery_store_views.xml',
        'views/website_landing_views.xml',
        'views/homepage_template.xml',
        'views/checkout_store_pickup_views.xml',
        'views/j_sale_order_pickup_views.xml',
        'views/sale_order_website_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_pincode_delivery_check/static/src/css/landing_page.css',
            'website_pincode_delivery_check/static/src/css/checkout_pickup.css',
            'website_pincode_delivery_check/static/src/js/landing_page.js',
            'website_pincode_delivery_check/static/src/js/checkout_pickup.js',
            'website_pincode_delivery_check/static/src/js/j_checkout_pickup.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
