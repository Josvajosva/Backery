from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def action_post(self):
        res = super(AccountMove, self).action_post()
        
        if self.move_type == 'out_invoice' and self.invoice_line_ids:
            _logger.info(f"=== INVOICE POSTED: {self.name} ===")
            grn = self.with_context(default_move_type=False, force_picking_type='incoming')._create_grn_from_invoice()
            if not grn:
                raise UserError(_(
                    'This seems to be a multi-company issue, so GRN is not created for relevant Purchase Order',
                ))
        return res

    def _create_grn_from_invoice(self):
        """Create GRN from invoice (Odoo 18, multi-company safe)"""
        try:
            # Anchor everything to the invoice company
            company = self.company_id
            invoice = self.sudo().with_company(company)

            _logger.info(
                "Creating GRN from Invoice=%s | Company=%s",
                invoice.name,
                company.name,
            )

            sale_orders = invoice._get_linked_sale_orders()

            for sale_order in sale_orders:
                sale_order = sale_order.sudo().with_company(company)

                _logger.info("Processing SO: %s", sale_order.name)

                # Get PO (no sudo tricks)
                po = sale_order.auto_purchase_order_id
                if not po:
                    _logger.info("SO %s has no linked PO", sale_order.name)
                    continue

                # IMPORTANT: do NOT force invoice company onto PO
                po = po.sudo().with_company(po.company_id)

                _logger.info(
                    "Found PO=%s | PO Company=%s",
                    po.name,
                    po.company_id.name,
                )

                partner = po.partner_id.sudo().with_company(po.company_id)

                if not partner.validate_grn_from_invoice:
                    _logger.info(
                        "Partner %s does not allow GRN from invoice",
                        partner.name,
                    )
                    continue

                _logger.info("✓ Creating GRN for PO: %s", po.name)

                # Pass records as-is; company is re-anchored inside the method
                invoice._create_grn_for_po_safely(po, sale_order)

            return True

        except Exception as e:
            _logger.error("Error in _create_grn_from_invoice: %s", str(e))
            import traceback
            _logger.error(traceback.format_exc())
            return False

    def _create_grn_from_invoice1(self):
        """Main method to create GRN from invoice"""
        try:
            _logger.info(f"Creating GRN for invoice: {self.name}")
            
            sale_orders = self._get_linked_sale_orders()
            
            for sale_order in sale_orders:
                _logger.info(f"Processing SO: {sale_order.name}")
                
                if sale_order.auto_purchase_order_id.sudo():
                    po = sale_order.auto_purchase_order_id.sudo()
                    _logger.info(f"Found PO via auto_purchase_order_id: {po.name}")
                elif sale_order.auto_purchase_order_id.sudo():
                    po = self._find_purchase_order(sale_order.auto_purchase_order_id.sudo())
                    _logger.info(f"Found PO via auto_purchase_order_id (legacy): {po.name if po else 'Not found'}")
                else:
                    _logger.info(f"SO {sale_order.name} has no linked PO")
                    continue
                po = po.sudo().with_company(po.company_id)
                if po and po.partner_id.sudo().validate_grn_from_invoice:
                    _logger.info(f"✓ Creating GRN for PO: {po.name}")
                    self._create_grn_for_po_safely(po, sale_order)
            return True                
        except Exception as e:
            _logger.error(f"Error in _create_grn_from_invoice: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return False
    
    def _create_grn_for_po_safely(self, po, sale_order):
        """Safe method to create GRN - avoids move_type conflict"""
        try:
            _logger.info(f"=== SAFE GRN CREATION FOR PO: {po.name} ===")
            
            invoice_lines = self._get_invoice_lines_for_so(sale_order)
            
            if not invoice_lines:
                _logger.warning(f"No invoice lines for SO {sale_order.name}")
                return
            
            picking = self._create_picking_safe(po)
            if not picking:
                picking = self._create_picking_manually(po)
            
            if not picking:
                _logger.error("Failed to create picking with both methods")
                return
            
            for invoice_line in invoice_lines:
                self._add_product_to_picking_safe(picking, po, invoice_line)
            
            self._validate_picking_safe(picking)
            
            _logger.info(f"✓ GRN created: {picking.name}")
            
        except Exception as e:
            _logger.error(f"Error creating GRN safely: {str(e)}")
    
    def _create_picking_safe(self, po):
        """Safe picking creation - avoids any move_type conflict"""
        try:
            picking_type = self.env['stock.picking.type'].with_context(
                default_move_type=False
            ).search([
                ('code', '=', 'incoming'),
                ('company_id', '=', po.company_id.id)
            ], limit=1)
            
            if not picking_type:
                picking_type = self.env.ref('stock.picking_type_in')
            
            _logger.info(f"Using picking type: {picking_type.name}")
            
            picking_vals = {
                'partner_id': po.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'origin': f"PO: {po.name}",
                'purchase_id': po.id,
                'company_id': po.company_id.id,
                'move_type': 'direct',
            }
            
            _logger.info(f"Creating picking with safe values")
            picking = self.env['stock.picking'].sudo().with_context(
                default_move_type='direct'
            ).create(picking_vals)
            
            _logger.info(f"✓ Picking created: {picking.name}")
            return picking
            
        except Exception as e:
            _logger.error(f"Error in safe picking creation: {str(e)}")
            return None
    
    def _create_picking_manually(self, po):
        """Manual picking creation as fallback"""
        try:
            _logger.info("Trying manual picking creation...")
            
            picking_type_id = self.env.ref('stock.picking_type_in').id
            
            picking_data = {
                'partner_id': po.partner_id.id,
                'picking_type_id': picking_type_id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': self.env.ref('stock.stock_location_stock').id,
                'purchase_id': po.id,
            }
            
            picking = self.env['stock.picking'].sudo().create(picking_data)
            
            picking.write({'origin': po.name})
            
            _logger.info(f"✓ Manual picking created: {picking.name}")
            return picking
            
        except Exception as e:
            _logger.error(f"Error in manual picking creation: {str(e)}")
            return None
    
    def _add_product_to_picking_safe(self, picking, po, invoice_line):
        """Add product to picking safely"""
        try:
            product = invoice_line.product_id
            quantity = invoice_line.quantity
            
            _logger.info(f"Adding product: {product.name}, Qty: {quantity}")
            
            po_line = po.order_line.filtered(
                lambda l: l.product_id.id == product.id
            )
            
            if not po_line:
                _logger.warning(f"No PO line found for product: {product.name}")
                return
            
            po_line = po_line[0]
            
            move_vals = {
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'purchase_line_id': po_line.id,
                'company_id': po_line.company_id.id,
            }
            
            move = self.env['stock.move'].sudo().create(move_vals)
            _logger.info(f"Move created: {move.id}")
            
            move_line_vals = {
                'move_id': move.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'qty_done': quantity,
                'picking_id': picking.id,
                'company_id': po_line.company_id.id,
            }
            
            self.env['stock.move.line'].sudo().create(move_line_vals)
            
            po_line.qty_received = quantity
            
        except Exception as e:
            _logger.error(f"Error adding product: {str(e)}")
    
    def _validate_picking_safe(self, picking):
        """Validate picking safely"""
        try:
            _logger.info(f"Validating picking: {picking.name}")
            picking = picking.sudo().with_company(picking.company_id)
            picking.action_confirm()
            _logger.info(f"Picking confirmed")
            
            for move_line in picking.move_line_ids:
                if move_line.qty_done == 0:
                    move_line.qty_done = move_line.product_uom_qty
            
            picking.button_validate()
            _logger.info(f"✓ Picking validated: {picking.name}")
            
        except Exception as e:
            _logger.error(f"Error validating picking: {str(e)}")
            try:
                picking._action_done()
                _logger.info(f"✓ Picking validated via _action_done")
            except Exception as e2:
                _logger.error(f"Secondary error: {str(e2)}")
    
    def _get_linked_sale_orders(self):
        return self.invoice_line_ids.mapped('sale_line_ids.order_id')
    
    def _find_purchase_order(self, po_number):
        """Legacy method - find PO by reference number"""
        if not po_number:
            return None
        
        po_number = str(po_number).strip()
        return self.env['purchase.order'].search([
            ('name', '=', po_number),
            ('state', 'in', ['purchase', 'done'])
        ], limit=1)
    
    def _get_invoice_lines_for_so(self, sale_order):
        return self.invoice_line_ids.filtered(
            lambda il: il.sale_line_ids and 
                      il.sale_line_ids[0].order_id.id == sale_order.id
        )
