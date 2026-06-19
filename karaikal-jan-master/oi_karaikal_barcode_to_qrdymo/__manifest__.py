# -*- coding: utf-8 -*-

{
    'name': 'OI Kifl Product QR Code Label (Dymo)',
    'version': '1.0',
    'summary': 'Replaces Dymo barcode labels with QR codes in product label reports',
    'description': """
        This module inherits the default Dymo product label report
        (product.report_simple_label_dymo) and replaces the barcode
        with a QR code while preserving the same layout and pricing details.
    """,
    'author': "OODU IMPLEMENTERS PRIVATE LIMITED",
    'website': "https://www.odooimplementers.com",
    'category': 'Product',
    'depends': ['product', 'mrp', 'contacts'],
    'data': [
        'report/report_product_label_qrcode.xml',
        'report/paperformat.xml',
        'views/mrp_production_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
