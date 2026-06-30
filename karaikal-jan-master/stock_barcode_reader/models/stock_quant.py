from odoo import models, api, _, fields
from odoo.exceptions import UserError

class StockLocation(models.Model):
    _inherit = 'stock.location'

    barcode_stock_take_location = fields.Boolean(
        string="Allow Location in Barcode Stock Take",
        help="If enabled, locations will be visible in the barcode stock take screen."
    )


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def get_barcode_locations(self):
        """Return all stock take locations."""
        locations = self.env["stock.location"].search([
            ("usage", "=", "internal"),
            ("company_id", "=", self.env.company.id),
            ("barcode_stock_take_location", "=", True),
        ], order="complete_name")
        if locations:
            vals = []
            if self.env.company.parent_id:
                vals.append({
                    'id': locations[0].id,
                    "name": locations[0].complete_name,

                })
            else:
                vals = [
                    {
                        "id": loc.id,
                        "name": loc.complete_name,
                    }
                    for loc in locations
                ]
            return vals
        return [{}]

    @api.model
    def barcode_apply_inventory(self, location_id, lines):
        location = self.env['stock.location'].browse(location_id)
        if not location.exists() or location.usage != 'internal':
            raise UserError(_("Please select a valid internal location."))

        if not lines:
            return True

        qty_map = {
            line['product_id']: line.get('quantity', 0)
            for line in lines
        }

        if any(qty < 0 for qty in qty_map.values()):
            raise UserError(_("Quantity must be positive."))

        product_ids = list(qty_map.keys())

        Quant = self.env['stock.quant'].sudo()

        existing_quants = Quant.search([
            ('product_id', 'in', product_ids),
            ('location_id', '=', location_id),
            ('lot_id', '=', False),
        ])

        existing_map = {q.product_id.id: q for q in existing_quants}

        to_create_vals = [
            {
                'product_id': pid,
                'location_id': location_id,
                'inventory_quantity': qty_map[pid],
            }
            for pid in product_ids
            if pid not in existing_map
        ]

        new_quants = Quant.create(to_create_vals) if to_create_vals else Quant.browse()

        to_update = existing_quants.filtered(
            lambda q: q.product_id.id in qty_map
        )

        if to_update:
            for quant in to_update:
                quant.inventory_quantity = qty_map[quant.product_id.id]

        all_quants = existing_quants | new_quants

        if all_quants:
            all_quants.sudo()._apply_inventory()
            all_quants.sudo().inventory_quantity_set = False
        return True
