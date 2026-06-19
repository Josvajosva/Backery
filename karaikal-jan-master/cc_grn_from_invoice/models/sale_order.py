from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('auto_purchase_order_id', None):
                po_rec = self.env['purchase.order'].search([('id','=',vals.get('auto_purchase_order_id'))])
                #vals['company_id'] = po_rec.company_id.id
        return super().create(vals_list)
