# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate default_code when creating variants with category"""
        for vals in vals_list:
            if not vals.get('default_code'):
                product_tmpl_id = vals.get('product_tmpl_id')
                if product_tmpl_id:
                    template = self.env['product.template'].browse(product_tmpl_id)
                    if template.categ_id and template.categ_id.prefix:
                        category = template.categ_id
                        next_code, used_number = category._get_next_product_code()
                        if next_code and used_number:
                            vals['default_code'] = next_code
                            next_sequence = used_number + 1
                            category.write({'number': next_sequence})
        return super().create(vals_list)