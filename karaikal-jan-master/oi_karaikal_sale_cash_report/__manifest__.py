# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Karaikal Reports",
    'summary': "This module is used to send/receive documents with PEPPOL",
    'description': """
            Sale,Cash,Petty Cash Report
            """,
    'version': '1.1',
    'depends': ['base','point_of_sale','sale_management','stock','account','hr','bi_sale_advance_payment'],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/wizard.xml",
        "views/account_payment.xml",
        "report/sale_cash_report.xml",
        
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
