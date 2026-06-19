# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date,timedelta


class CrmLead(models.Model):
    _inherit = 'product.template'


    product_expiry = fields.Selection([
        ('near_expiry','Near Expiry'),
        ('recall','Recall'),
        ('expired','Expired')
    ], string="Product Expiry", copy=False, compute='_compute_product_expiry') 
    show_expiry_warning = fields.Boolean(string="Show Expiry Warning", copy=False)
    show_recall_warning = fields.Boolean(string="Show Recall Warning", copy=False)
    shelf_life_days = fields.Integer(
        string="Product Shelf Life (Days)", default=0)


    @api.depends('expiration_time','alert_time')
    def _compute_product_expiry(self):
        for record in self:
            if record.expiration_time:
                expiry_date = date.today() + timedelta(days=record.expiration_time)
                if expiry_date == date.today():
                    record.product_expiry = 'expired'
                    record.show_expiry_warning = True
                    record.show_recall_warning = False
                elif expiry_date - timedelta(days=1) == date.today():
                    record.product_expiry = 'recall'
                    record.show_recall_warning = True
                    record.show_expiry_warning = False
                else:
                    record.product_expiry = ''
                    record.show_expiry_warning = False
                    record.show_recall_warning = False
            else:
                record.product_expiry = ''
                record.show_expiry_warning = False
                record.show_recall_warning = False
