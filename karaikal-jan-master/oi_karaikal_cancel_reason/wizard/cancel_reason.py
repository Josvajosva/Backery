# -*- coding: utf-8 -*-
from odoo import fields, models

class CancelReasonCapture(models.TransientModel):
    _name = 'cancel.reason.capture'
    _description= 'Capture the Cancel Reason'
    
    reason_id = fields.Many2one(comodel_name="stock.picking.cancel.reason", string="Reason", required=True)
    
    def button_confirm(self):
        self.ensure_one()
        obj_stock_picking = self.env["stock.picking"]
        act_close = {"type": "ir.actions.act_window_close"}
        picking_ids = self._context.get("active_ids")
        if picking_ids is None:
            return act_close
        assert len(picking_ids) == 1, "Only 1 picking ID expected"
        picking = obj_stock_picking.browse(picking_ids)
        picking.cancel_reason_id = self.reason_id.id
        picking.action_cancel()
        return act_close