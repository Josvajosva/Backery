{
    "name": "Stock Barcode Reader",
    "version": "18.0.1.1.0",
    "category": "Inventory",
    "summary": "Barcode-based physical inventory counting",
    "depends": [
        "stock",
    ],
    "data": [
        "views/barcode_views.xml",
        "views/stock_location_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcode_reader/static/src/js/barcode_action.scss",
            "stock_barcode_reader/static/src/js/barcode_action.js",
            "stock_barcode_reader/static/src/js/barcode_action.xml",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
