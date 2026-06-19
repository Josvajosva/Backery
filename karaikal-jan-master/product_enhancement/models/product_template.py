# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    type_master_id = fields.Many2one(
        'type.master',
        string='Type Master',
        help="Type master for this product"
    )

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Product Category'),
            'template': '/product_enhancement/static/xls/product.xlsx'
        }]