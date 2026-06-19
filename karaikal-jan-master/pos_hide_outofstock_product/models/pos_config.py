# -*- coding: utf-8 -*-

from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'

    hide_outofstock_products = fields.Boolean(
        string="Hide Out of Stock Products",
        help="If enabled, out-of-stock products will be hidden from the POS product list."
    )
    
    
    



