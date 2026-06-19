from odoo import api,fields, models

class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    xml_id = fields.Char('External ID', compute='_compute_xml_id', help="ID of the action if defined in a XML file")
    
    
    def _compute_xml_id(self):
        res = self.get_external_id()
        for action in self:
            action.xml_id = res.get(action.id)

    sales_price_total = fields.Float(
        string='Total Sales Price',
        compute='_compute_sales_price_total',
        store=True,
    )

    cost_price_total = fields.Float(
        string='Total Cost Value',
        compute='_compute_cost_price_total',
        store=True,
    )

    @api.depends('scrap_qty', 'product_id.lst_price')
    def _compute_sales_price_total(self):
        for record in self:
            record.sales_price_total = record.scrap_qty * record.product_id.lst_price


    @api.depends('scrap_qty','product_id.standard_price')
    def _compute_cost_price_total(self):
        for record in self:
            record.cost_price_total = record.scrap_qty * record.product_id.standard_price
            


             
# class QualityPoint(models.Model):
#     _inherit = "quality.point"

#     @api.constrains('measure_on', 'picking_type_ids')
#     def _check_measure_on(self):
#         return True
