# -*- coding: utf-8 -*-

import io
import base64

import xlsxwriter

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    prefix = fields.Char(string="Prefix")
    starting_number = fields.Integer(string="Starting Number", default=1)
    number = fields.Integer(string="Number", readonly=True, copy=False)

    def _get_next_product_code(self):
        if not self.prefix:
            return False, 0
        
        if self.number > 0:
            next_number = self.number
        else:
            next_number = self.starting_number

        formatted_number = str(next_number).zfill(3)
        return f"{self.prefix}{formatted_number}", next_number

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Product Category'),
            'template': '/product_enhancement/static/xls/product_category.xlsx'
        }]