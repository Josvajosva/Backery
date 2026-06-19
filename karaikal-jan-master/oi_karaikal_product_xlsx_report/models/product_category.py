# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    exclude_from_stock_report = fields.Boolean(
        string='Exclude from Stock Report',
        help='If checked, products in this category will not be included in the Combined Stock Report.'
    )

    inventory_summary_type = fields.Selection([
        ('fg', 'FG'),
        ('sfg', 'SFG'),
        ('rm', 'RM'),
        ('pm', 'PM & Consumables'),
    ], string='Inventory Summary Mapping', help="Map this category to the corresponding column in the Inventory Valuation Summary Report.")
