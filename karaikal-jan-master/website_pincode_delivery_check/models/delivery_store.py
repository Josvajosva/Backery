# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DeliveryStore(models.Model):
    _name = 'delivery.store'
    _description = 'Delivery Store'
    _order = 'name'

    name = fields.Char(string='Store Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    state_id = fields.Many2one('res.country.state', string='State')
    main_pincode = fields.Char(string='Main Pincode', required=True)
    active = fields.Boolean(string='Active', default=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    delivery_radius = fields.Float(string='Delivery Radius (KM)', default=20.0,
        help="If greater than 0, pincodes within this radius from the store will be allowed for delivery.")
    map_html = fields.Html(string='Coverage Map', compute='_compute_map_html', sanitize=False)
    deliverable_pincode_ids = fields.One2many('delivery.store.pincode', 'store_id', string='Deliverable Pincodes')

    @api.depends('latitude', 'longitude', 'delivery_radius', 'name')
    def _compute_map_html(self):
        for store in self:
            if store.latitude and store.longitude:
                escaped_name = store.name.replace("'", "\\'") if store.name else "Store"
                srcdoc = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    <style> body, html, #map {{ margin: 0; padding: 0; height: 100%; width: 100%; }} </style>
                </head>
                <body>
                    <div id="map"></div>
                    <script>
                        var map = L.map('map').setView([{store.latitude}, {store.longitude}], 10);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                            maxZoom: 18,
                            attribution: '© OpenStreetMap'
                        }}).addTo(map);
                        var marker = L.marker([{store.latitude}, {store.longitude}]).addTo(map);
                        marker.bindPopup("<b>{escaped_name}</b><br>Radius: {store.delivery_radius} km").openPopup();
                        var circle = L.circle([{store.latitude}, {store.longitude}], {{
                            color: 'red',
                            fillColor: '#f03',
                            fillOpacity: 0.2,
                            radius: {store.delivery_radius * 1000.0}
                        }}).addTo(map);
                        map.fitBounds(circle.getBounds());
                    </script>
                </body>
                </html>
                """
                srcdoc_escaped = srcdoc.replace('"', '&quot;')
                store.map_html = f'<iframe srcdoc="{srcdoc_escaped}" style="width: 100%; height: 400px; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></iframe>'
            else:
                store.map_html = '<div style="padding: 20px; text-align: center; background: #f8f9fa; border: 1px dashed #ccc; border-radius: 8px; color: #6c757d;"><i>Fetch coordinates to view the coverage map.</i></div>'

    @api.onchange('main_pincode')
    def _onchange_main_pincode(self):
        if self.main_pincode:
            pincode_clean = self.main_pincode.strip().upper()
            self.main_pincode = pincode_clean
            # Search res.city in company's country for matching zipcode
            country_id = self.env.company.country_id.id
            domain = [('zipcode', '=', pincode_clean)]
            if country_id:
                domain.append(('country_id', '=', country_id))
            city_rec = self.env['res.city'].sudo().search(domain, limit=1)
            if city_rec and city_rec.state_id:
                self.state_id = city_rec.state_id

    @api.constrains('main_pincode')
    def _check_main_pincode(self):
        for store in self:
            if not store.main_pincode or not store.main_pincode.strip():
                raise ValidationError(_("Main Pincode cannot be blank."))

    def action_fetch_coordinates(self):
        for store in self:
            if store.main_pincode:
                lat, lon = self.env['delivery.store.pincode']._get_pincode_coordinates(store.main_pincode)
                if lat is not None and lon is not None:
                    store.latitude = lat
                    store.longitude = lon
                else:
                    raise ValidationError(_("Could not fetch coordinates for pincode %s" % store.main_pincode))


class DeliveryStorePincode(models.Model):
    _name = 'delivery.store.pincode'
    _description = 'Deliverable Pincode'
    _order = 'pincode'
    _rec_name = 'pincode'

    store_id = fields.Many2one('delivery.store', string='Store', required=True, ondelete='cascade')
    pincode = fields.Char(string='Pincode', required=True, index=True)
    state_id = fields.Many2one('res.country.state', string='State')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('store_pincode_uniq', 'unique(store_id, pincode)', 'This deliverable pincode is already configured for this store!'),
    ]

    @api.onchange('pincode')
    def _onchange_pincode(self):
        if self.pincode:
            pincode_clean = self.pincode.strip().upper()
            self.pincode = pincode_clean
            # Search res.city in company's country for matching zipcode
            country_id = self.env.company.country_id.id
            domain = [('zipcode', '=', pincode_clean)]
            if country_id:
                domain.append(('country_id', '=', country_id))
            city_rec = self.env['res.city'].sudo().search(domain, limit=1)
            if city_rec and city_rec.state_id:
                self.state_id = city_rec.state_id

    @api.constrains('pincode')
    def _check_pincode(self):
        for record in self:
            if not record.pincode or not record.pincode.strip():
                raise ValidationError(_("Pincode cannot be blank."))

    @api.model
    def is_pincode_deliverable(self, pincode, store_id=None):
        if not pincode:
            return False
        pincode_clean = pincode.strip().upper()
        # Search for any active deliverable pincode under an active store (exact match)
        domain = [
            ('pincode', '=ilike', pincode_clean),
            ('active', '=', True),
            ('store_id.active', '=', True)
        ]
        if store_id:
            domain.append(('store_id', '=', store_id))
            
        count = self.search_count(domain)
        if count > 0:
            return True
            
        # Radius based matching
        radius_domain = [
            ('active', '=', True),
            ('delivery_radius', '>', 0),
            ('latitude', '!=', 0.0),
            ('longitude', '!=', 0.0),
        ]
        if store_id:
            radius_domain.append(('id', '=', store_id))
            
        stores_with_radius = self.env['delivery.store'].sudo().search(radius_domain)
        if stores_with_radius:
            target_lat, target_lon = self._get_pincode_coordinates(pincode_clean)
            if target_lat is not None and target_lon is not None:
                for store in stores_with_radius:
                    dist = self._calculate_distance(store.latitude, store.longitude, target_lat, target_lon)
                    if dist <= store.delivery_radius:
                        return True
                        
        return False

    @api.model
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        import math
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @api.model
    def _get_pincode_coordinates(self, pincode):
        cache_rec = self.env['pincode.location.cache'].sudo().search([('pincode', '=', pincode)], limit=1)
        if cache_rec:
            if cache_rec.not_found:
                return None, None
            return cache_rec.latitude, cache_rec.longitude
            
        import requests
        try:
            url = f"https://nominatim.openstreetmap.org/search?postalcode={pincode}&countrycodes=in&format=json"
            headers = {'User-Agent': 'CIBON-ERP/1.0 (admin@cibon.com)'}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    self.env['pincode.location.cache'].sudo().create({
                        'pincode': pincode,
                        'latitude': lat,
                        'longitude': lon,
                    })
                    return lat, lon
                else:
                    self.env['pincode.location.cache'].sudo().create({
                        'pincode': pincode,
                        'not_found': True,
                    })
        except Exception:
            pass
        return None, None


class PincodeLocationCache(models.Model):
    _name = 'pincode.location.cache'
    _description = 'Pincode Location Cache'

    pincode = fields.Char(string='Pincode', required=True, index=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    not_found = fields.Boolean(string='Not Found', default=False)

