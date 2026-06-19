from odoo import fields, models, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    work_center_id = fields.Many2one(comodel_name='mrp.workcenter', string="Work Center",store =True,compute="_compute_work_cender_id")

    @api.depends('production_ids')
    def _compute_work_cender_id(self):
        for order in self:
            if order.production_ids:
                mrp_order_id = order.production_ids[0]
                order.work_center_id = mrp_order_id.product_id.work_center_id