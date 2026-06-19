# -*- coding: utf-8 -*-
from odoo import fields, models,api

    
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    product_category_id = fields.Many2one('product.category', string="Product Category")



class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, change_default=True, tracking=True, check_company=True, help="You can find a vendor by its Name, TIN, Email or Internal Reference.",default=lambda self: self.env.ref('base.main_company').id,)

    purchase_type = fields.Selection([
        ('daily_intent', 'Daily Intent'),
        ('special_order', 'Special Order')
    ], string="Purchase Type", default='daily_intent',copy=False)
    
    sales_types = fields.Selection([
        ('walk_in_customers', 'Walk-in Customers (POS)'),
        ('sale_order_mto', 'Sale Order (MTO)'),
        ('corporate_orders', 'Corporate Orders'),
        ('custom_cakes', 'Custom Cakes'),
        ('wholesale_supply', 'Wholesale Supply'),
        ('food_aggregators', 'Food Aggregators'),
        ('webstore_sales', 'Webstore Sales'),
    ], string="Sales Types",copy=False)

    @api.model
    def _prepare_sale_order_line_data(self, line, company):
        
        sale_order_line_data = super(PurchaseOrder, self)._prepare_sale_order_line_data(line, company)
        sale_order_line_data['product_category_id'] = line.product_category_id.id if line.product_category_id else False
        return sale_order_line_data
    
    def _prepare_sale_order_data(self, name, partner, company, direct_delivery_address):
        
        values = super(PurchaseOrder, self)._prepare_sale_order_data(name, partner, company, direct_delivery_address)
        values.update({
            'purchase_type': self.purchase_type,  
        })
        return values
    