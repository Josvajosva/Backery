# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.http import request
from odoo.osv import expression

class Website(models.Model):
    _inherit = 'website'

    def sale_product_domain(self):
        domain = super().sale_product_domain()
        if not request or not getattr(request, 'session', None):
            return domain

        delivery_option = request.session.get('delivery_option')
        if not delivery_option or delivery_option == 'pan_india':
            return domain

        company_id = False
        # Try to get the company_id from current cart first
        website = self if len(self) == 1 else (request.website if request and getattr(request, 'website', None) else self.env['website'])
        order = website.sale_get_order() if website else False
        if order and order.company_id:
            company_id = order.company_id.id
        else:
            # If no cart is created yet, determine the company_id from session info
            if delivery_option == 'store_pickup':
                store_id = request.session.get('pickup_store_id')
                if store_id:
                    store = self.env['delivery.store'].sudo().browse(store_id)
                    if store and store.company_id:
                        company_id = store.company_id.id
            elif delivery_option == 'local_delivery':
                zip_code = request.session.get('local_delivery_zip')
                if zip_code:
                    store_pincode = self.env['delivery.store.pincode'].sudo().search([
                        ('pincode', '=ilike', zip_code.upper()),
                        ('active', '=', True),
                        ('store_id.active', '=', True)
                    ], limit=1)
                    store = store_pincode.store_id if store_pincode else self.env['delivery.store']
                    if not store:
                        stores_with_radius = self.env['delivery.store'].sudo().search([
                            ('active', '=', True),
                            ('delivery_radius', '>', 0),
                            ('latitude', '!=', 0.0),
                            ('longitude', '!=', 0.0),
                        ])
                        target_lat, target_lon = self.env['delivery.store.pincode']._get_pincode_coordinates(zip_code)
                        if target_lat is not None and target_lon is not None:
                            for s in stores_with_radius:
                                dist = self.env['delivery.store.pincode']._calculate_distance(s.latitude, s.longitude, target_lat, target_lon)
                                if dist <= s.delivery_radius:
                                    store = s
                                    break
                    if store and store.company_id:
                        company_id = store.company_id.id

        if company_id:
            domain = expression.AND([domain, [('company_id', 'in', [company_id, False])]])
            # Query stock.quant directly for the outlet's warehouse stock location.
            # Searching product.template with qty_available > 0 via with_context(warehouse=...)
            # aggregates global stock and ignores the outlet scope — stock.quant is exact.
            warehouse = self.env['stock.warehouse'].sudo().search(
                [('company_id', '=', company_id)], limit=1
            )
            if warehouse:
                quants = self.env['stock.quant'].sudo().search([
                    ('location_id', 'child_of', warehouse.lot_stock_id.id),
                    ('quantity', '>', 0),
                ])
                in_stock_template_ids = quants.mapped('product_id.product_tmpl_id').ids
                if in_stock_template_ids:
                    domain = expression.AND([domain, [('id', 'in', in_stock_template_ids)]])
                else:
                    # No stock at this outlet — show empty shop (correct behaviour)
                    domain = expression.AND([domain, [('id', '=', False)]])

        return domain

    def _get_fiscal_position_for_company(self, company, partner):
        """Return a fiscal position valid for the given company."""
        if not company:
            return self.env['account.fiscal.position']
        return self.env['account.fiscal.position'].with_company(company).sudo()._get_fiscal_position(
            partner,
            delivery=partner,
        )

    def _prepare_sale_order_values(self, partner_sudo):
        values = super()._prepare_sale_order_values(partner_sudo)
        if not request:
            return values

        delivery_option = request.session.get('delivery_option')
        if delivery_option == 'store_pickup':
            store_id = request.session.get('pickup_store_id')
            if store_id:
                store = self.env['delivery.store'].sudo().browse(store_id)
                if store and store.company_id:
                    values['company_id'] = store.company_id.id
                    values['pickup_store_id'] = store.id
                    warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', store.company_id.id)], limit=1)
                    if warehouse:
                        values['warehouse_id'] = warehouse.id
            values['delivery_option'] = 'store_pickup'
        elif delivery_option == 'local_delivery':
            zip_code = request.session.get('local_delivery_zip')
            if zip_code:
                # Find matching store for local delivery
                store_pincode = self.env['delivery.store.pincode'].sudo().search([
                    ('pincode', '=ilike', zip_code.upper()),
                    ('active', '=', True),
                    ('store_id.active', '=', True)
                ], limit=1)
                store = store_pincode.store_id if store_pincode else self.env['delivery.store']
                if not store:
                    stores_with_radius = self.env['delivery.store'].sudo().search([
                        ('active', '=', True),
                        ('delivery_radius', '>', 0),
                        ('latitude', '!=', 0.0),
                        ('longitude', '!=', 0.0),
                    ])
                    target_lat, target_lon = self.env['delivery.store.pincode']._get_pincode_coordinates(zip_code)
                    if target_lat is not None and target_lon is not None:
                        for s in stores_with_radius:
                            dist = self.env['delivery.store.pincode']._calculate_distance(s.latitude, s.longitude, target_lat, target_lon)
                            if dist <= s.delivery_radius:
                                store = s
                                break
                if store and store.company_id:
                    values['company_id'] = store.company_id.id
                    warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', store.company_id.id)], limit=1)
                    if warehouse:
                        values['warehouse_id'] = warehouse.id
            values['delivery_option'] = 'local_delivery'
        elif delivery_option == 'pan_india':
            values['delivery_option'] = 'pan_india'

        company_id = values.get('company_id')
        if company_id and company_id != self.company_id.id:
            company = self.env['res.company'].browse(company_id)
            fpos = self._get_fiscal_position_for_company(company, partner_sudo)
            if fpos:
                values['fiscal_position_id'] = fpos.id

        return values
