from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_is_zero


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_intercompany_so_invoice = fields.Boolean(
        compute='_compute_intercompany_so_invoice',
        #store=True,
    )
    intercompany_so_name = fields.Char(
        compute='_compute_intercompany_so_invoice',
        #store=True,
    )
    intercompany_so_qr_image = fields.Boolean()

    @api.depends('move_type', 'line_ids.sale_line_ids.order_id')
    def _compute_intercompany_so_invoice(self):
        for move in self:
            so_names = ''
            is_intercompany = False
            if move.move_type == 'out_invoice':
                sale_orders = move.line_ids.sale_line_ids.order_id
                intercompany_sos = sale_orders.filtered(
                    lambda so: so.auto_purchase_order_id
                )
                if intercompany_sos:
                    is_intercompany = True
                    so_names = ', '.join(intercompany_sos.mapped('name'))
            move.is_intercompany_so_invoice = is_intercompany
            move.intercompany_so_name = so_names

    def _get_intercompany_so_ids(self):
        """Return comma-separated SO IDs. Kept for compatibility."""
        self.ensure_one()
        sale_orders = self.line_ids.sale_line_ids.order_id
        intercompany_sos = sale_orders.filtered(lambda so: so.auto_purchase_order_id)
        return ','.join(str(so.id) for so in intercompany_sos)

    def _get_intercompany_po_ids(self):
        """Return comma-separated PO IDs for QR code. Called from report template."""
        self.ensure_one()
        sale_orders = self.line_ids.sale_line_ids.order_id
        intercompany_sos = sale_orders.filtered(lambda so: so.auto_purchase_order_id)
        po_ids = intercompany_sos.mapped('auto_purchase_order_id')
        return ','.join(str(po.id) for po in po_ids)

    def get_intercompany_so_qr_code(self):
        """Generate and return a base64 encoded QR code image data URI for the intercompany invoice."""
        self.ensure_one()
        so_ids = self._get_intercompany_po_ids()
        if not so_ids:
            return ""
        qr_value = f"{so_ids}|{self.id}"
        try:
            import qrcode
            import base64
            from io import BytesIO
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=0,
            )
            qr.add_data(qr_value)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            
            return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
        except Exception:
            return ""


    def action_post(self):
        """Override to update product vendor prices when vendor bill is confirmed"""
        res = super().action_post()
        for move in self:
            if move.move_type == 'in_invoice' and move.state == 'posted':
                self._update_product_vendor_prices(move)
        return res

    def _update_product_vendor_prices(self, move):
        """Update product cost from posted vendor bill lines linked to a purchase order.

        Uses one BOM search for all changed components (not one search per line).
        """
        company = move.company_id

        lines = move.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        )
        if not lines:
            return

        precision = company.currency_id.decimal_places
        company_currency = company.currency_id
        convert_date = (
            move.invoice_date
            or move.date
            or fields.Date.context_today(self)
        )

        # Last matching line wins if the same product appears on multiple bill lines.
        product_id_to_price = {}
        for line in lines:
            if not (line.purchase_line_id or line.purchase_order_id):
                continue
            line_currency = line.currency_id or move.currency_id
            if line_currency == company_currency:
                price_company = line.price_unit
            else:
                price_company = line_currency._convert(
                    line.price_unit,
                    company_currency,
                    company,
                    convert_date,
                )
            product_id_to_price[line.product_id.id] = price_company

        if not product_id_to_price:
            return

        Product = self.env['product.product'].sudo()
        write_ctx = {**self.env.context, 'disable_auto_svl': True}
        updated_product_ids = []

        for product_id, price_company in product_id_to_price.items():
            product = Product.browse(product_id)
            if float_compare(
                product.standard_price, price_company, precision_digits=precision
            ) == 0:
                continue

            product.with_context(**write_ctx).write({'standard_price': price_company})
            product.product_tmpl_id._sync_branch_vendor_price_from_factory(company, self.partner_id)
            updated_product_ids.append(product.id)
            updated_product_ids.append(product_id)
        if not updated_product_ids:
            return

        domain = [
            ('product_id', 'in', list(set(updated_product_ids))),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ]
        boms = self.env['mrp.bom.line'].sudo().search(domain).mapped('bom_id')
        tmpl_ids = list(dict.fromkeys(boms.mapped('product_tmpl_id').ids))
        ProductTemplate = self.env['product.template'].sudo()
        for tmpl_id in tmpl_ids:
            product = ProductTemplate.browse(tmpl_id)
            product.button_bom_cost()


    def _get_invoice_quantities_by_product(self, invoice):
        """Return dict product_id (id) -> quantity in product UoM (from invoice lines)."""
        product_lines = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == "product" and l.product_id
        )
        product_lines.mapped('product_id.uom_id')
        product_lines.mapped('product_uom_id')
        qtys = {}
        for line in product_lines:
            pid = line.product_id.id
            if line.product_uom_id != line.product_id.uom_id:
                qty = line.product_uom_id._compute_quantity(
                    line.quantity, line.product_id.uom_id, round=False
                )
            else:
                qty = line.quantity
            qtys[pid] = qtys.get(pid, 0) + qty
        return qtys

    @api.model
    def action_confirm(self, scan_input):
        def _response(level, message, action=None):
            res = {"ok": True, "level": level, "message": message}
            if isinstance(action, dict) and action.get("type"):
                res["action"] = action
            return res

        try:
            po_id_str, invoice_id_str = (p.strip() for p in str(scan_input or "").strip().split("|", 1))
            po_id = int(po_id_str)
            invoice_id = int(invoice_id_str)
        except Exception as e:
            raise ValidationError(_("Please scan a valid QR code (format: PO_id|Invoice_id).")) from e

        purchase_order = self.env["purchase.order"].sudo().browse(po_id)
        if not purchase_order.exists():
            raise ValidationError(_("Purchase Order %s not found.") % po_id_str)

        invoice = self.env["account.move"].sudo().browse(invoice_id)
        if not invoice.exists():
            raise ValidationError(_("Invoice %s not found.") % invoice_id_str)
        if invoice.move_type not in ("out_invoice", "in_invoice"):
            raise ValidationError(_("Document is not an invoice."))
        if invoice.state != "posted":
            raise ValidationError(_("Only posted (confirmed) invoices can be used. Please confirm the invoice first."))

        if invoice.id in purchase_order.scanned_invoice_ids.ids:
            raise ValidationError(
                _("Invoice %s has already been scanned for Purchase Order %s.")
                % (invoice.name, purchase_order.name)
            )

        invoice_qtys = self._get_invoice_quantities_by_product(invoice)

        invoice_pids = set(pid for pid, qty in invoice_qtys.items() if qty > 0)
        po_pids = set(purchase_order.order_line.mapped('product_id.id'))
        extra_pids = invoice_pids - po_pids
        if extra_pids:
            extra_products = self.env['product.product'].browse(extra_pids).mapped('display_name')
            raise ValidationError(_("Invoice contains products not found in the Purchase Order: %s. Only Purchase Order products are allowed.") % ", ".join(extra_products))

        # Group-wise handling: get all pickings belonging to the procurement group(s) of the purchase order
        group_ids = purchase_order.order_line.mapped('group_id')
        if not group_ids and purchase_order.group_id:
            group_ids = purchase_order.group_id

        if group_ids:
            open_pickings = self.env['stock.picking'].search([
                ('group_id', 'in', group_ids.ids),
                ('state', 'not in', ('done', 'cancel'))
            ])
        else:
            open_pickings = purchase_order.picking_ids.filtered(
                lambda p: p.state not in ("done", "cancel")
            )

        if not open_pickings:
            raise ValidationError(
                _("GRN is already validated for Purchase Order: %s.")
                % purchase_order.name
            )

        # Check if any single PO in the group has multiple pending receipts (backorders)
        for po in open_pickings.mapped('purchase_id'):
            po_pickings = open_pickings.filtered(lambda p: p.purchase_id == po)
            if len(po_pickings) > 1:
                raise ValidationError(
                    _("Cannot proceed: Purchase Order %s has multiple pending receipts (e.g., backorders). Please process them manually in Odoo.")
                    % po.name
                )

        picking = open_pickings

        perf_ctx = {
            "mail_notrack": True,
            "tracking_disable": True,
            "mail_create_nolog": True,
            "mail_activity_automation_skip": True,
        }
        picking = picking.with_context(**perf_ctx)
        if picking.state in ("draft", "waiting"):
            picking.action_confirm()

        active_moves = picking.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel") and m.product_id
        )

        moves_to_update = self.env["stock.move"]
        for move in active_moves:
            inv_qty = invoice_qtys.get(move.product_id.id, 0)
            rounding = move.product_uom.rounding

            if move.product_id.uom_id != move.product_uom:
                inv_qty_in_move_uom = move.product_id.uom_id._compute_quantity(
                    inv_qty, move.product_uom, round=False
                )
            else:
                inv_qty_in_move_uom = inv_qty

            if float_is_zero(inv_qty, precision_rounding=rounding):
                continue

            move.quantity = inv_qty_in_move_uom
            moves_to_update |= move

        if not moves_to_update:
            # Check if invoice products are already in done moves of the PO
            invoice_pids = [pid for pid, qty in invoice_qtys.items() if qty > 0]
            done_moves = purchase_order.picking_ids.move_ids.filtered(
                lambda m: m.state == 'done' and m.product_id.id in invoice_pids
            )
            if done_moves:
                # Find the exact picking(s) that match the invoice quantities
                matching_pickings = []
                for picking in done_moves.picking_id:
                    picking_qtys = {}
                    for move in picking.move_ids.filtered(lambda m: m.state == 'done'):
                        pid = move.product_id.id
                        if move.product_uom != move.product_id.uom_id:
                            qty = move.product_uom._compute_quantity(
                                move.quantity, move.product_id.uom_id, round=False
                            )
                        else:
                            qty = move.quantity
                        picking_qtys[pid] = picking_qtys.get(pid, 0) + qty

                    match = True
                    for pid, inv_qty in invoice_qtys.items():
                        if inv_qty <= 0:
                            continue
                        pick_qty = picking_qtys.get(pid, 0)
                        product = self.env['product.product'].browse(pid)
                        rounding = product.uom_id.rounding
                        if float_compare(inv_qty, pick_qty, precision_rounding=rounding) != 0:
                            match = False
                            break
                    if match:
                        matching_pickings.append(picking)

                display_picking_ids = [p.id for p in (matching_pickings if matching_pickings else done_moves.picking_id)]
                done_pickings = self.env['stock.picking'].browse(display_picking_ids).filtered(lambda p: p.name)

                if done_pickings:
                    grn_names = ", ".join(done_pickings.mapped('name'))
                    raise ValidationError(
                        _("Invoice %s has already been completed for Purchase Order %s in GRN %s.")
                        % (invoice.name, purchase_order.name, grn_names)
                    )
                raise ValidationError(
                    _("Invoice %s has already been completed for Purchase Order %s.")
                    % (invoice.name, purchase_order.name)
                )

            raise ValidationError(
                _("Product quantities in the Invoice do not match the pending receipt (%s).") % picking.name
            )

        moves_to_update.write({"picked": True})

        validate_ctx = {
            'skip_backorder': True,
            'skip_sanity_check': True,
            'button_validate_picking_ids': picking.ids,
            'from_qr_scan': True,
            'scan_po_id': purchase_order.id,
            'scan_invoice_id': invoice.id,
            **perf_ctx,
        }
        res = picking.with_context(**validate_ctx)._pre_action_done_hook()
        if res is not True:
            if isinstance(res, dict) and res.get('context'):
                new_context = dict(res['context'])
                new_context['scan_po_id'] = purchase_order.id
                new_context['scan_invoice_id'] = invoice.id
                res['context'] = new_context
            elif isinstance(res, dict):
                res['context'] = {
                    'scan_po_id': purchase_order.id,
                    'scan_invoice_id': invoice.id,
                }
            return _response("warning", _("Receipt needs additional steps."), action=res)

        picking.with_context(cancel_backorder=False, from_qr_scan=True, **perf_ctx)._action_done()

        purchase_order.sudo().write({
            'scanned_invoice_ids': [(4, invoice.id)],
        })

        return _response("success", _("Purchase order receipt validated successfully."))


class ConfirmExpiryInherit(models.TransientModel):
    _inherit = 'expiry.picking.confirmation'

    def process(self):
        res = super().process()
        if self.env.context.get('from_qr_scan'):
            self._save_scanned_invoice()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("Purchase order receipt validated successfully."),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        return res

    def process_no_expired(self):
        res = super().process_no_expired()
        if self.env.context.get('from_qr_scan'):
            self._save_scanned_invoice()
            return {'type': 'ir.actions.act_window_close'}
        return res

    def _save_scanned_invoice(self):
        po_id = self.env.context.get('scan_po_id')
        invoice_id = self.env.context.get('scan_invoice_id')
        if po_id and invoice_id:
            po = self.env['purchase.order'].sudo().browse(po_id)
            if po.exists():
                po.write({'scanned_invoice_ids': [(4, invoice_id)]})
