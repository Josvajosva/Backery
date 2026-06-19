# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.http import request

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        if request and getattr(request, 'is_frontend', False):
            try:
                order = request.website.sale_get_order()
                if order and order.delivery_option in ['store_pickup', 'local_delivery']:
                    for vals in vals_list:
                        if 'company_id' in vals:
                            vals['company_id'] = False
            except Exception:
                pass
        return super().create(vals_list)

    def write(self, vals):
        if 'company_id' in vals and request and getattr(request, 'is_frontend', False):
            try:
                order = request.website.sale_get_order()
                if order and order.delivery_option in ['store_pickup', 'local_delivery']:
                    vals['company_id'] = False
            except Exception:
                pass
        return super().write(vals)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_option = fields.Selection([
        ('pan_india', 'PAN India Delivery'),
        ('local_delivery', 'Local Delivery'),
        ('store_pickup', 'In-Store Pickup')
    ], string='Delivery Option', default='pan_india')

    pickup_store_id = fields.Many2one('delivery.store', string='Pickup Store')

    pickup_type = fields.Selection([
        ('asap', 'ASAP'),
        ('scheduled', 'Scheduled'),
    ], string='Pickup Type', default='asap')

    scheduled_pickup_datetime = fields.Datetime(string='Scheduled Pickup Time')

    def _ensure_compatible_partners(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id') or (self.company_id.id if self else False)
            if not company_id:
                continue
            partner_ids = [vals.get(f) for f in ['partner_id', 'partner_invoice_id', 'partner_shipping_id'] if vals.get(f)]
            if self:
                for f in ['partner_id', 'partner_invoice_id', 'partner_shipping_id']:
                    if f not in vals:
                        pid = getattr(self, f).id
                        if pid:
                            partner_ids.append(pid)
            if partner_ids:
                partners = self.env['res.partner'].sudo().browse(partner_ids)
                modified = self.env['res.partner']
                for partner in partners:
                    if partner.company_id and partner.company_id.id != company_id:
                        partner.company_id = False
                        modified |= partner
                if modified:
                    modified.flush_recordset(['company_id'])

    @api.model_create_multi
    def create(self, vals_list):
        # Clean up partner companies if they don't match the order's company
        self._ensure_compatible_partners(vals_list)

        # We need to temporarily remove website_id if the company_id in vals
        # is different from the website's company_id, to bypass Odoo's core website-company mismatch check.
        website_to_restore = []
        for vals in vals_list:
            if vals.get('website_id') and vals.get('company_id'):
                website = self.env['website'].browse(vals['website_id'])
                if website.company_id.id != vals['company_id']:
                    website_to_restore.append(vals['website_id'])
                    vals['website_id'] = False
                    continue
            website_to_restore.append(False)

        orders = super().create(vals_list)

        for order, website_id in zip(orders, website_to_restore):
            if website_id:
                order.sudo().write({'website_id': website_id})

        return orders

    def _sync_fiscal_position_with_company(self):
        """Align fiscal position with order company (multi-store website carts)."""
        for order in self:
            fpos = order.fiscal_position_id
            if not order.company_id or not fpos or not fpos.company_id:
                continue
            if fpos.company_id == order.company_id:
                continue
            partner = order.partner_shipping_id or order.partner_id
            new_fpos = self.env['account.fiscal.position'].with_company(order.company_id).sudo()._get_fiscal_position(
                order.partner_id,
                delivery=partner,
            )
            if new_fpos:
                super(SaleOrder, order).write({'fiscal_position_id': new_fpos.id})

    def write(self, vals):
        self._ensure_compatible_partners([vals])
        if vals.get('company_id') and 'fiscal_position_id' not in vals and len(self) == 1 and self.partner_id:
            company = self.env['res.company'].browse(vals['company_id'])
            partner = self.partner_shipping_id or self.partner_id
            fpos = self.env['account.fiscal.position'].with_company(company).sudo()._get_fiscal_position(
                self.partner_id,
                delivery=partner,
            )
            if fpos:
                vals = dict(vals, fiscal_position_id=fpos.id)
        return super().write(vals)

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        self._sync_fiscal_position_with_company()
        return super()._cart_update(
            product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs
        )

    # @api.constrains('partner_shipping_id', 'state', 'order_line')
    # def _check_delivery_pincode(self):
    #     for order in self:
    #         # Only validate if:
    #         # 1. State is in draft (Quotation), sent (Quotation Sent), or sale (Sales Order)
    #         # 2. The order requires delivery (physical products exist in the order lines)
    #         if order.website_id and order.state in ['draft', 'sent', 'sale'] and order._has_deliverable_products():
    #             # For In-Store Pickup, skip pincode validation
    #             if order.delivery_option == 'store_pickup':
    #                 continue
    #             # For Local Delivery and PAN India, validate shipping pincode
    #             if order.partner_shipping_id:
    #                 zip_code = order.partner_shipping_id.zip
    #                 if zip_code:
    #                     store = False
    #                     if order.delivery_option == 'local_delivery':
    #                         store = self.env['delivery.store'].sudo().search([('company_id', '=', order.company_id.id)], limit=1)
    #
    #                     is_deliverable = self.env['delivery.store.pincode'].sudo().is_pincode_deliverable(
    #                         zip_code, store_id=store.id if store else None
    #                     )
    #                     if not is_deliverable:
    #                         raise ValidationError(_("Delivery is not available for this pincode."))
    #                 else:
    #                     raise ValidationError(_("Delivery is not available because the shipping address has no pincode."))
