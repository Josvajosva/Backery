# -*- coding: utf-8 -*-
from odoo import fields, models,api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    product_category_id = fields.Many2one('product.category', string="Product Category")

class saleOrder(models.Model):
    _inherit = "sale.order"


    purchase_type = fields.Selection([
        ('daily_intent', 'Daily Intent'),
        ('special_order', 'Special Order')
    ], string="Purchase Type",copy=False)
    
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
    def _prepare_purchase_order_line_data(self, so_line, date_order, company):
        
        po_line_data = super(saleOrder, self)._prepare_purchase_order_line_data(so_line, date_order, company)
        po_line_data['product_category_id'] = so_line.product_id.categ_id.id  
        return po_line_data