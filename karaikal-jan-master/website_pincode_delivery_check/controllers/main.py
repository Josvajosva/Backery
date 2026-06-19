# -*- coding: utf-8 -*-
import logging

import werkzeug
from markupsafe import Markup
from werkzeug.urls import url_encode

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import ensure_db
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class WebsitePincodeSale(WebsiteSale):

    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
    ], type='http', auth="public", website=True, sitemap=WebsiteSale.sitemap_shop)
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        if request.env.user._is_public():
            return request.redirect('/web/login?redirect=/landing')
        if not request.session.get('delivery_option'):
            return request.redirect('/landing')
        return super().shop(page=page, category=category, search=search, min_price=min_price, max_price=max_price, ppg=ppg, **post)

    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=WebsiteSale.sitemap_products, readonly=True)
    def product(self, product, category='', search='', **kwargs):
        if request.env.user._is_public():
            return request.redirect('/web/login?redirect=/landing')
        if not request.session.get('delivery_option'):
            return request.redirect('/landing')
        return super().product(product, category=category, search=search, **kwargs)

    def _validate_address_values(self, address_values, partner_sudo, address_type, use_delivery_as_billing, required_fields, is_main_address, **kwargs):
        # Call super first to collect any default Odoo address validation errors
        invalid_fields, missing_fields, error_messages = super()._validate_address_values(
            address_values, partner_sudo, address_type, use_delivery_as_billing, required_fields, is_main_address, **kwargs
        )

        order_sudo = request.website.sale_get_order()
        # Only validate pincode if the cart requires delivery (has physical/deliverable products)
        if order_sudo and order_sudo._has_deliverable_products() and order_sudo.delivery_option != 'store_pickup':
            # Check pincode if creating/editing shipping address, or billing address used as shipping
            if address_type == 'delivery' or use_delivery_as_billing:
                zip_val = address_values.get('zip')
                if zip_val:
                    store = False
                    if order_sudo.delivery_option == 'local_delivery':
                        store = request.env['delivery.store'].sudo().search([('company_id', '=', order_sudo.company_id.id)], limit=1)

                    is_deliverable = request.env['delivery.store.pincode'].sudo().is_pincode_deliverable(
                        zip_val, store_id=store.id if store else None
                    )
                    if not is_deliverable:
                        invalid_fields.add('zip')
                        if store:
                            error_messages.append(
                                _("Sorry, delivery service to pincode %s is not available from our selected store %s.") % (zip_val, store.name)
                            )
                        else:
                            error_messages.append(
                                _("Sorry, delivery service is not available for pincode %s.") % zip_val
                            )
                else:
                    invalid_fields.add('zip')
                    error_messages.append(_("Pincode is required for delivery validation."))

        return invalid_fields, missing_fields, error_messages

    def _get_shop_payment_errors(self, order):
        # Call super first to get standard payment errors
        errors = super()._get_shop_payment_errors(order)

        # Check if shipping pincode is deliverable
        if order and order._has_deliverable_products() and order.delivery_option != 'store_pickup':
            shipping_zip = order.partner_shipping_id.zip
            if shipping_zip:
                store = False
                if order.delivery_option == 'local_delivery':
                    store = request.env['delivery.store'].sudo().search([('company_id', '=', order.company_id.id)], limit=1)

                is_deliverable = request.env['delivery.store.pincode'].sudo().is_pincode_deliverable(
                    shipping_zip, store_id=store.id if store else None
                )
                if not is_deliverable:
                    if store:
                        errors.append((
                            _("Delivery Service Unavailable"),
                            _("Sorry, delivery service to pincode %s is not available from our selected store %s.") % (shipping_zip, store.name)
                        ))
                    else:
                        errors.append((
                            _("Delivery Service Unavailable"),
                            _("Sorry, delivery service is not available for pincode %s.") % shipping_zip
                        ))
            else:
                errors.append((
                    _("Missing Delivery Pincode"),
                    _("Please provide a valid delivery pincode for your shipping address.")
                ))
        return errors

    def _check_addresses(self, order_sudo):
        # Call super first to check if addresses are complete
        res = super()._check_addresses(order_sudo)
        if res:
            return res

        # Additional validation: if the shipping zip code is not deliverable, redirect back
        if (
            order_sudo
            and order_sudo._has_deliverable_products()
            and order_sudo.delivery_option != 'store_pickup'
        ):
            shipping_zip = order_sudo.partner_shipping_id.zip
            store = False
            if order_sudo.delivery_option == 'local_delivery':
                store = request.env['delivery.store'].sudo().search([('company_id', '=', order_sudo.company_id.id)], limit=1)

            if not shipping_zip or not request.env['delivery.store.pincode'].sudo().is_pincode_deliverable(
                shipping_zip, store_id=store.id if store else None
            ):
                partner_id = order_sudo.partner_shipping_id.id or order_sudo.partner_id.id
                return request.redirect(
                    f'/shop/address?partner_id={partner_id}&address_type=delivery&pincode_error=1'
                )


class WebsitePickupSchedule(http.Controller):

    @http.route('/shop/save_pickup_schedule', type='json', auth='public', website=True)
    def save_pickup_schedule(self, pickup_type, scheduled_datetime=None, **kwargs):
        order = request.website.sale_get_order()
        if not order:
            return {'status': 'error', 'message': 'No active order found.'}
        from datetime import datetime, timedelta
        vals = {'pickup_type': pickup_type}
        if pickup_type == 'scheduled' and scheduled_datetime:
            try:
                scheduled_dt = datetime.strptime(
                    scheduled_datetime[:16].replace('T', ' '), '%Y-%m-%d %H:%M'
                )
            except Exception:
                return {'status': 'error', 'message': 'Invalid datetime format.'}
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            max_date = today_start + timedelta(days=2, hours=23, minutes=59)
            if scheduled_dt < now:
                return {'status': 'error', 'message': 'Pickup time must be in the future.'}
            if scheduled_dt < today_start or scheduled_dt > max_date:
                return {
                    'status': 'error',
                    'message': 'Pickup can only be scheduled for today or up to 2 days ahead.',
                }
            vals['scheduled_pickup_datetime'] = scheduled_dt
        else:
            vals['scheduled_pickup_datetime'] = False
        order.sudo().write(vals)
        return {'status': 'success'}


class WebsiteLanding(http.Controller):

    @http.route('/landing', type='http', auth='public', website=True)
    def landing_page(self, **kwargs):
        # Fetch all delivery stores that have a company associated
        stores = request.env['delivery.store'].sudo().search([('active', '=', True), ('company_id', '!=', False)])

        # Get current selection from session if any
        current_option = request.session.get('delivery_option', '')
        current_store_id = request.session.get('pickup_store_id', 0)
        current_zip = request.session.get('local_delivery_zip', '')

        values = {
            'stores': stores,
            'current_option': current_option,
            'current_store_id': current_store_id,
            'current_zip': current_zip,
        }
        return request.render('website_pincode_delivery_check.landing_page_template', values)

    @http.route('/landing/select', type='json', auth='public', website=True)
    def landing_select(self, delivery_option, **kwargs):
        request.session['delivery_option'] = delivery_option
        store_id = 0
        zip_code = ''
        store = False

        if delivery_option == 'store_pickup':
            store_id = int(kwargs.get('store_id', 0))
            if not store_id:
                return {'status': 'error', 'message': 'Please select a store.'}
            request.session['pickup_store_id'] = store_id
            request.session.pop('local_delivery_zip', None)
        elif delivery_option == 'local_delivery':
            zip_code = kwargs.get('zip_code', '').strip()
            if not zip_code:
                return {'status': 'error', 'message': 'Please enter a pincode.'}

            # Find matching store for local delivery
            store_pincode = request.env['delivery.store.pincode'].sudo().search([
                ('pincode', '=ilike', zip_code.upper()),
                ('active', '=', True),
                ('store_id.active', '=', True)
            ], limit=1)
            store = store_pincode.store_id if store_pincode else request.env['delivery.store']
            if not store:
                stores_with_radius = request.env['delivery.store'].sudo().search([
                    ('active', '=', True),
                    ('delivery_radius', '>', 0),
                    ('latitude', '!=', 0.0),
                    ('longitude', '!=', 0.0),
                ])
                target_lat, target_lon = request.env['delivery.store.pincode']._get_pincode_coordinates(zip_code)
                if target_lat is not None and target_lon is not None:
                    for s in stores_with_radius:
                        dist = request.env['delivery.store.pincode']._calculate_distance(s.latitude, s.longitude, target_lat, target_lon)
                        if dist <= s.delivery_radius:
                            store = s
                            break
            if not store:
                return {'status': 'error', 'message': f'Sorry, local delivery is not available for pincode {zip_code}.'}

            request.session['local_delivery_zip'] = zip_code
            request.session.pop('pickup_store_id', None)
        else:
            request.session.pop('pickup_store_id', None)
            request.session.pop('local_delivery_zip', None)

        # Update existing cart if it exists
        order = request.website.sale_get_order()
        if order and order.state == 'draft':
            vals = {}
            if delivery_option == 'store_pickup':
                store = request.env['delivery.store'].sudo().browse(store_id)
                if store:
                    vals['company_id'] = store.company_id.id
                    vals['pickup_store_id'] = store.id
                    warehouse = request.env['stock.warehouse'].sudo().search([('company_id', '=', store.company_id.id)], limit=1)
                    if warehouse:
                        vals['warehouse_id'] = warehouse.id
                vals['delivery_option'] = 'store_pickup'
            elif delivery_option == 'local_delivery':
                if store:
                    vals['company_id'] = store.company_id.id
                    warehouse = request.env['stock.warehouse'].sudo().search([('company_id', '=', store.company_id.id)], limit=1)
                    if warehouse:
                        vals['warehouse_id'] = warehouse.id
                vals['delivery_option'] = 'local_delivery'
                vals['pickup_store_id'] = False
            else:
                vals['company_id'] = request.website.company_id.id
                warehouse = request.env['stock.warehouse'].sudo().search([('company_id', '=', request.website.company_id.id)], limit=1)
                if warehouse:
                    vals['warehouse_id'] = warehouse.id
                vals['delivery_option'] = 'pan_india'
                vals['pickup_store_id'] = False

            if vals.get('company_id'):
                company = request.env['res.company'].browse(vals['company_id'])
                fpos = request.website._get_fiscal_position_for_company(company, order.partner_id)
                if fpos:
                    vals['fiscal_position_id'] = fpos.id

            order.write(vals)

        return {'status': 'success'}


class WebsiteSignup(AuthSignupHome):
    """Redirect portal users to /landing after signup/login (never /odoo backend)."""

    def _portal_redirect(self, redirect=None):
        redirect = redirect or request.params.get('redirect') or '/landing'
        return redirect if redirect.startswith('/') else '/landing'

    def _is_portal_session(self):
        uid = request.session.uid
        if not uid:
            return False
        if uid == request.env.ref('base.public_user').id:
            return False
        return not request.env['res.users'].sudo().browse(uid)._is_internal()

    def _login_redirect(self, uid, redirect=None):
        if not request.env['res.users'].sudo().browse(uid)._is_internal():
            return self._portal_redirect(redirect)
        return super()._login_redirect(uid, redirect=redirect)

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        redirect_url = self._portal_redirect(kw.get('redirect'))

        if self._is_portal_session():
            return request.redirect(redirect_url)

        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                if not request.env['ir.http']._verify_request_recaptcha_token('signup'):
                    raise UserError(_("Suspicious activity detected by Google reCaptcha."))
                self.do_signup(qcontext)
            except UserError as e:
                if request.session.uid and request.session.uid != request.env.ref('base.public_user').id:
                    return request.redirect(redirect_url)
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                if request.env['res.users'].sudo().search_count(
                    [('login', '=', qcontext.get('login'))], limit=1
                ):
                    if request.session.uid and request.session.uid != request.env.ref('base.public_user').id:
                        return request.redirect(redirect_url)
                    qcontext['error'] = _("Another user is already registered using this email address.")
                else:
                    _logger.warning("%s", e)
                    qcontext['error'] = _("Could not create a new account.") + Markup('<br/>') + str(e)
            else:
                return request.redirect(redirect_url)

        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search([
                ('email', '=', qcontext.get('signup_email')),
                ('state', '!=', 'new'),
            ], limit=1)
            if user:
                return request.redirect('/web/login?%s' % url_encode({
                    'login': user.login,
                    'redirect': redirect_url,
                }))

        if self._is_portal_session():
            return request.redirect(redirect_url)

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @http.route()
    def web_login(self, *args, **kw):
        kw.setdefault('redirect', '/landing')
        ensure_db()
        response = super(AuthSignupHome, self).web_login(*args, **kw)
        if not hasattr(response, 'qcontext'):
            return response
        response.qcontext.update(self.get_auth_signup_config())
        if self._is_portal_session() and request.httprequest.method == 'GET' and request.params.get('redirect'):
            return request.redirect(
                self._login_redirect(request.session.uid, redirect=request.params.get('redirect'))
            )
        return response
