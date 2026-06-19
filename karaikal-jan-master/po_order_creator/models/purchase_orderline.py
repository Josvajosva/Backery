from odoo import models, fields, api

class PurchaseOrderline(models.Model):
    _inherit = 'purchase.order.line'