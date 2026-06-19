from odoo import models
from odoo.tools.float_utils import float_compare, float_round


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        auto_generate = self.env['ir.config_parameter'].sudo().get_param('auto_generate_lot_number.is_auto_generate')
        if auto_generate:
            serial_number_type = self.env['ir.config_parameter'].sudo().get_param('auto_generate_lot_number.serial_number_type')
            prefix = self.env['ir.config_parameter'].sudo().get_param('auto_generate_lot_number.prefix', default='')
            digits = int(self.env['ir.config_parameter'].sudo().get_param('auto_generate_lot_number.digits', default=0))
            if serial_number_type == 'global':
                pass
                sequence = self.env['ir.sequence'].create({'code': 'res.config.code', 'name': 'Res config code'})
                if sequence:
                    lot_name = sequence.next_by_code('res.config.code')
                    lot_name = f"{prefix}{lot_name.zfill(digits)}"
                    vals.update({'lot_name': lot_name})
            else:
                vals.update({'lot_name': self.product_id.product_tmpl_id._number_next_actual()})
        return vals

    def action_show_details(self):
        """This used to overriden 'view_stock_move_operations' view"""
        res = super(StockMove, self).action_show_details()
        auto_generate = self.env['ir.config_parameter'].sudo().get_param(
            'auto_generate_lot_number.is_auto_generate')
        if auto_generate:
            view = self.env.ref('auto_generate_lot_number'
                                '.view_stock_move_operations')
            res.update({
                'views': [(view.id, 'form')],
                'view_id': view.id,
            })
        return res