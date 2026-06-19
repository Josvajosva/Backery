# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Karaikal Receipt",
    'summary': "This module is used to send/receive documents with PEPPOL",
    'description': """
        - Register as a PEPPOL participant
        - Send and receive documents via PEPPOL network in Peppol BIS Billing 3.0 format
            """,
    'version': '1.1',
    'depends': ['base','point_of_sale','oi_karaikal_company_inherit','helpdesk_whatsapp_integration'],
    "data": [],
    'license': 'LGPL-3',
    'assets': {
        'point_of_sale._assets_pos': [
            'oi_karaikal_receipt/static/src/js/pos_receipt.js',
            'oi_karaikal_receipt/static/src/xml/hsn_hide.xml',
            'oi_karaikal_receipt/static/src/xml/reciept_header.xml',
            'oi_karaikal_receipt/static/src/xml/order_line_receipt.xml',
            'oi_karaikal_receipt/static/src/xml/order_widget.xml',
            'oi_karaikal_receipt/static/src/js/order_widget.js',
        ],
    },
}
