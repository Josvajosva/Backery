from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _action_done(self, cancel_backorder=False):
        moves_to_process = self.env['stock.move']
        
        for move in self:
            '''if move.purchase_line_id:
                if move.purchase_line_id.order_id.partner_id.validate_grn_from_invoice:
                    _logger.info(f"Skipping automatic validation for move {move.id} - vendor has GRN validation enabled")
                    continue
                else:
                    moves_to_process += move
            else:'''
            moves_to_process += move
        
        if moves_to_process:
            return super(StockMove, moves_to_process)._action_done(cancel_backorder=cancel_backorder)
        return True
    
    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        if self.purchase_line_id:
            if self.purchase_line_id.order_id.partner_id.validate_grn_from_invoice:
                _logger.info(f"Blocking picking creation for move {self.id}")
                return {}
        return vals
