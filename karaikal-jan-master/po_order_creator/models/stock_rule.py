# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.purchase_stock.models.stock_rule import StockRule as PurchaseStockRule


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company_id, values, partner):
        domain = super()._make_po_get_domain(company_id, values, partner)
        domain_list = list(domain)
        if values.get('group_id'):
            domain_list = [d for d in domain_list if d[0] != 'group_id']
            domain_list.append(('group_id', '=', values['group_id'].id))
        return tuple(domain_list)

    def _prepare_purchase_order(self, company_id, origins, values):
        res = super()._prepare_purchase_order(company_id, origins, values)
        if values and isinstance(values[0], dict):
            has_orderpoint = any(
                v.get('orderpoint_id') for v in values 
                if isinstance(v, dict)
            )
            if has_orderpoint:
                res['is_auto_created'] = True
        return res
