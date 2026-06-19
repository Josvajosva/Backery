from odoo import models, fields, api,_
from odoo.exceptions import ValidationError


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"


    def _prepare_procurement_values(self, date=False, group=False):
        res = super()._prepare_procurement_values(date=date, group=group)
        if res.get('orderpoint_id'):
            unique_group = self.env['procurement.group'].create({
                'name': f'{self.name} - {fields.Datetime.now()}',
            })
            res['group_id'] = unique_group

        return res

    def create_purchase_orders_from_orderpoints(self):
        """
        Automatically create purchase orders when stock is reduced.
        This method can be called from stock moves or scheduled actions.
        """
        orderpoints = self.search([
            ('trigger', '=', 'auto'),
            ('active', '=', True),
            ('product_id.active', '=', True),
        ])

        if orderpoints:
            orderpoints_to_procure = orderpoints.filtered(
                lambda orderpoint: orderpoint.qty_forecast < orderpoint.product_min_qty
                and orderpoint.qty_to_order > 0
                and (not orderpoint.snoozed_until or fields.Date.today() > orderpoint.snoozed_until)
            )
            if orderpoints_to_procure:
                for orderpoint in orderpoints_to_procure:
                    orderpoint_sudo = orderpoint.sudo()
                    try:
                        orderpoint_sudo._procure_orderpoint_confirm(
                            use_new_cursor=False,
                            company_id=self.env.company,
                            raise_user_error=False
                        )
                    except Exception as e:
                        continue


    def update_purchase_orders(self):
        purchase_orders = self.env['purchase.order'].search([
            ('state', 'in', ['draft', 'sent']),
            ('is_auto_created', '=', True),
        ])
        for po in purchase_orders:
            try:
                po.button_confirm()
                # pickings = po.picking_ids.filtered(
                #     lambda p: p.state not in ('done', 'cancel')
                # )
                # for picking in pickings:
                #     try:
                #         if picking.state == 'draft':
                #             picking.action_confirm()
                #         if picking.state in ('waiting', 'confirmed'):
                #             picking.action_assign()
                #         if picking.state == 'assigned':
                #             for move in picking.move_ids_without_package:
                #                 if move.quantity == 0:
                #                     move.quantity = move.product_uom_qty
                #             picking.button_validate()
                #     except Exception as e:
                #         continue
            except Exception as e:
                continue

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Replenishment'),
            'template': '/account/static/xls/replenishment_import_template.xlsx'
        }]
