from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    @api.model_create_multi
    def create(self, vals_list):
        orders = self.browse()
        for vals in vals_list:
            orders |= super(PurchaseOrder, self).create(vals)
        
            #if record.partner_id.validate_grn_from_invoice:
            #    _logger.info(f"PO {record.name} created for vendor with GRN validation: {record.partner_id.name}")
        
        return orders

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        
        if self.partner_id.validate_grn_from_invoice:
            _logger.info(f"PO {self.name} confirmed for vendor with GRN validation: {self.partner_id.name}")
            
            draft_pickings = self.picking_ids.filtered(
                lambda p: p.state in ['draft', 'waiting', 'confirmed', 'assigned']
            )
            
            if draft_pickings:
                _logger.info(f"Cancelling {len(draft_pickings)} draft pickings for PO {self.name}")
                draft_pickings.action_cancel()
            
            for line in self.order_line:
                line.qty_received_method = 'manual'
                line.qty_received = 0.0
                _logger.debug(f"Set line {line.id} to manual qty received")
        
        return res
    
    def _create_picking(self):
        if self.partner_id.validate_grn_from_invoice:
            _logger.info(f"Skipping automatic picking creation for PO {self.name}")
            return self.env['stock.picking']
        return super(PurchaseOrder, self)._create_picking()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    def _update_received_qty_from_grn(self):
        """Update received quantity based on GRN"""
        for line in self:
            if line.order_id.partner_id.validate_grn_from_invoice:
                done_moves = self.env['stock.move'].search([
                    ('purchase_line_id', '=', line.id),
                    ('state', '=', 'done'),
                    ('picking_id.state', '=', 'done')
                ])
                
                if done_moves:
                    total_received = sum(done_moves.mapped('quantity_done'))
                    line.qty_received = total_received
                    _logger.info(f"Updated received qty for line {line.id}: {total_received}")
