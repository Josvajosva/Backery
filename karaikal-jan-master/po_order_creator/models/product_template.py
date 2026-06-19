# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import ValidationError, UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _sync_branch_vendor_price_from_factory(self, factory_company=None, partner_id=None):
        self.ensure_one()
        SupplierInfo = self.env['product.supplierinfo'].sudo()

        company_ids = factory_company.child_ids or factory_company
        partner_id = partner_id
        for company_id in company_ids:
            if not company_id.parent_id:
                continue
            branch_currency = company_id.parent_id.currency_id
            domain = [
                ('product_tmpl_id', '=', self.id),
                ('partner_id', '=', partner_id.id),
                ('company_id', '=', company_id.id),
            ]
            branch_suppliers = SupplierInfo.search(domain)
            if branch_suppliers:
                branch_suppliers.write({'price': self.standard_price})
            # else:
            #     SupplierInfo.create({
            #         'product_tmpl_id': self.id,
            #         'partner_id': company_id.partner_id.id,
            #         'company_id': company_id.id,
            #         'price': self.standard_price,
            #         'currency_id': branch_currency.id,
            #         'min_qty': 0.0,
            #     })