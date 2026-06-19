from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    computed_cost = fields.Float(string="Total Cost", store=True)
    new_cost = fields.Float(string="Unit Cost", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.computed_cost = record.product_id.standard_price * record.quantity
            record.new_cost = record.product_id.standard_price
        return records
