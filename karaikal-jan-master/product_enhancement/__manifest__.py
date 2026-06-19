{
    "name": "Product Enhancement",
    "summary": "Product management enhancements with auto-sequence codes, type master, and supplier part numbers",
    "version": "18.0.1.0.0",
    "category": "Sales/Product",
    "author": "Your Name",
    "license": "LGPL-3",
    "depends": ["base", "product", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/type_master_views.xml",
        "views/product_category_views.xml",
        "views/product_template_views.xml",
        "views/product_supplierinfo_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
