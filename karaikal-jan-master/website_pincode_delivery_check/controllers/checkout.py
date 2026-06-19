# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.delivery import Delivery


class CheckoutStorePickup(Delivery):

    @http.route('/shop/delivery_methods', type='json', auth='public', website=True)
    def shop_delivery_methods(self):
        order_sudo = request.website.sale_get_order()
        delivery_methods = order_sudo._get_delivery_methods()
        if request.session.get('delivery_option') == 'store_pickup':
            delivery_methods = delivery_methods.filtered(
                lambda dm: dm.name == 'In-Store Pickup'
            )

        values = {
            'delivery_methods': delivery_methods,
            'selected_dm_id': order_sudo.carrier_id.id,
            'order': order_sudo,
        }
        values |= self._get_additional_delivery_context()
        return request.env['ir.ui.view']._render_template('website_sale.delivery_form', values)