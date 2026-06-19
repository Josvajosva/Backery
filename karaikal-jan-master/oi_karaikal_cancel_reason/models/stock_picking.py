# -*- coding: utf-8 -*-
from odoo import fields, models

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    cancel_reason_id = fields.Many2one(
        comodel_name="stock.picking.cancel.reason",
        string="Reason for cancellation",
        readonly=True,
        ondelete="restrict",
        tracking=True,
        copy=False
    )

class StockPickingCancelReason(models.Model):
    _name = "stock.picking.cancel.reason"
    _description = "Stock Picking Cancel Reason"

    name = fields.Char(string="Reason", required=True)