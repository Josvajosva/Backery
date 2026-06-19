from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """Override to update product vendor prices when vendor bill is confirmed"""
        res = super().action_post()
        for move in self:
            if move.move_type == 'in_invoice' and move.state == 'posted':
                self._update_product_vendor_prices(move)
        return res

    def _update_product_vendor_prices(self, move):
        """Update product vendor prices based on confirmed purchase order amounts"""
        for line in move.invoice_line_ids:
            if not line.purchase_line_id or not line.product_id:
                continue

            purchase_line = line.purchase_line_id
            product = line.product_id
            partner_id = purchase_line.order_id.partner_id
            vendor = partner_id if not partner_id.parent_id else partner_id.parent_id

            if not vendor or not product:
                continue

            po_price = purchase_line.price_unit

            supplier_info = self.env['product.supplierinfo'].search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('partner_id', '=', vendor.id),
                # ('company_id', '=', move.company_id.id),
            ], limit=1)

            if supplier_info:
                supplier_info.write({
                    'price': po_price,
                    'currency_id': purchase_line.currency_id.id,
                })

            company_partner = (move.company_id.parent_id or move.company_id).partner_id

            is_inter_company = company_partner in (
                    vendor | vendor.parent_id
            )

            if is_inter_company:
                product.sudo().with_context(disable_auto_svl=True).write({
                    'standard_price': po_price
                })

