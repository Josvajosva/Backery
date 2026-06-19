# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Karaikal POS Company Extension",
    'summary': "Extends res.company with custom field and integrates it into POS",
    'description': """This module inherits the res.company model to add a custom field, 
                   which is then made available and used within the Point of Sale (POS) interface.""",
    'version': '1.1',
    'depends': ['base', 'point_of_sale'],
    "data": [
        "views/partner_company_inherit_views.xml",
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
