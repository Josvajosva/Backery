from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_auto_created = fields.Boolean(
        string='Auto Created',
        default=False,
        help='Indicates if this purchase order was automatically created from orderpoint by cron'
    )
    scanned_invoice_ids = fields.Many2many(
        'account.move',
        'purchase_order_scanned_invoice_rel',
        'purchase_order_id',
        'invoice_id',
        string='Scanned Invoices',
        copy=False,
    )


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.constrains('product_id')
    def _check_duplicate_products(self):
        for line in self:
            if not line.product_id or not line.order_id:
                continue
            duplicate_count = line.order_id.order_line.filtered(
                lambda l: l.product_id == line.product_id and l.id != line.id
            )
            if duplicate_count:
                raise ValidationError(
                    _("Duplicate product '%s' found. Please merge them into one line.")
                    % line.product_id.display_name
                )