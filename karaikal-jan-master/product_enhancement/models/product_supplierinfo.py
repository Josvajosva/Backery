# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    part_number = fields.Char(string="Part Number", help="Part number for this vendor")