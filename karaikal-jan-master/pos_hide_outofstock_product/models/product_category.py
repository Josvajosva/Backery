# -*- coding: utf-8 -*-

from odoo import fields, models, api, _

class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    always_visible_in_pos = fields.Boolean(
        string="Always Visible in POS",
        default=False,
        help="Even, out-of-stock products is enabled, these products will be list out in POS."
    )


    def _load_pos_data_fields(self, config_id):
        # Adds your custom field to the list of fields loaded into POS
        params = super()._load_pos_data_fields(config_id)
        params.append('always_visible_in_pos')
        return params


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    def _load_pos_data_fields(self, config_id):
        # Adds your custom field to the list of fields loaded into POS
        params = super()._load_pos_data_fields(config_id)
        params.append('qty_available')
        return params
