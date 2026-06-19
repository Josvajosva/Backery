from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _check_manual_validation_allowed(self):
        for picking in self:
            if picking.picking_type_id.code == 'incoming' and picking.purchase_id:
                is_from_qr = self.env.context.get('from_qr_scan')
                has_validate_group = self.env.user.has_group('po_order_creator.group_validate_picking')
                is_factory_company = (
                    (picking.company_id and picking.company_id.name == 'KARAIKAL IYANGARS FOODS LIMITED - PY') or
                    (self.env.company and self.env.company.name == 'KARAIKAL IYANGARS FOODS LIMITED - PY')
                )
                if not (is_from_qr or has_validate_group or is_factory_company):
                    raise ValidationError(_("Purchase GRN cannot be validated manually. Please scan the QR code to validate."))

    def button_validate(self):
        self._check_manual_validation_allowed()
        return super().button_validate()

    def _action_done(self):
        self._check_manual_validation_allowed()
        return super()._action_done()

    def action_validate_group_wise(self):
        # Find all unique procurement groups of the selected pickings
        groups = self.mapped('group_id').filtered(lambda g: g)
        if groups:
            # Search for all pending pickings in those groups
            pickings_to_validate = self.env['stock.picking'].search([
                ('group_id', 'in', groups.ids),
                ('state', 'not in', ('done', 'cancel'))
            ])
        else:
            pickings_to_validate = self

        return pickings_to_validate.button_validate()
