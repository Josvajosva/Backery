# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    attachment_ids = fields.Many2many('ir.attachment',string='Attachments', copy=False)
    hide_attachment = fields.Boolean(string="Hide Attachment", compute='_compute_hide_attachment', copy=False)
    # Already "opportunity_id" field exists in the "sale_crm" module.
    opportunity_id = fields.Many2one(copy=False)


    @api.depends('opportunity_id')
    def _compute_hide_attachment(self):
        for record in self:
            record.hide_attachment = bool(record.opportunity_id)
