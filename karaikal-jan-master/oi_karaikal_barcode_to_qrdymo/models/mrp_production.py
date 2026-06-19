from odoo import models, fields, api
from datetime import timedelta, date


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    use_by_date = fields.Date(string="Use By Date", compute="_compute_use_by_date", store=True, tracking=True)

    @api.depends('product_id', 'date_finished')
    def _compute_use_by_date(self):
        for rec in self:
            if rec.product_id:
                days = rec.product_id.shelf_life_days or 0
                today = date.today()
                rec.use_by_date = today + timedelta(days=days - 1) if days > 0 else today
            else:
                rec.use_by_date = False


class ResPartner(models.Model):
    _inherit = 'res.partner'

    property_product_pricelist = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        tracking=True
    )
