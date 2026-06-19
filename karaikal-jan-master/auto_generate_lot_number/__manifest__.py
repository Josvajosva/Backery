# -*- coding: utf-8 -*-
{
    "name": "Auto Generate Serial/Lot number",
    "version": "18.0",
    "category": "Purchases",
    "summary": "Generate And Manage Lot and Serial Numbers.",
    "description": "Auto generate lot/serial number on click of validate "
    "button in purchase order.",
    "author": "Cybrosys Techno Solutions",
    "company": "Cybrosys Techno Solutions",
    "maintainer": "Cybrosys Techno Solutions",
    "website": "https://www.cybrosys.com",
    "depends": ["stock", "purchase", "mrp"],
    "data": [
        "views/stock_move_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_template_views.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}