# Stock.py for OI Karaikal Product Report
from odoo import fields, models, api, _

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    previous_on_hand_qty = fields.Float(string="Previous On Hand Qty", digits='Product Unit of Measure')
    inventory_quntaity = fields.Float(string="Inventory Quantity", digits='Product Unit of Measure')


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _apply_inventory(self):
        # Store previous quantities before they are updated by apply_inventory
        quants_dict = {quant.id: {'qty': quant.quantity, 'inv_qty': quant.inventory_quantity} for quant in self}
        
        res = super()._apply_inventory()
        
        MoveLine = self.env["stock.move.line"]
        
        for rec in self:
            previous_qty = quants_dict.get(rec.id, {}).get('qty', 0.0)
            inv_qty = quants_dict.get(rec.id, {}).get('inv_qty', 0.0)
            
            domain = [
                ("product_id", "=", rec.product_id.id),
                ("lot_id", "=", rec.lot_id.id),
                "|",
                ("location_id", "=", rec.location_id.id),
                ("location_dest_id", "=", rec.location_id.id),
            ]
            move_line = MoveLine.search(domain, order="create_date desc, id desc", limit=1)
            
            if move_line:
                 move_line.write({
                     'previous_on_hand_qty': previous_qty,
                     'inventory_quntaity': inv_qty,
                 })
        
        return res
