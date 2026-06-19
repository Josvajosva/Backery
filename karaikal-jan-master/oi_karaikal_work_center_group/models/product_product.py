from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    work_center_id = fields.Many2one(comodel_name='mrp.workcenter',string="Work Center")