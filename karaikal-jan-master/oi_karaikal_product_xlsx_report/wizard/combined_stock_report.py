# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from collections import defaultdict
from odoo.exceptions import ValidationError
from datetime import date, timedelta, datetime
import io
import xlsxwriter
import base64


class CombinedStockReport(models.TransientModel):
    _name = 'combined.stock.report'
    _description = 'Combined Stock Report (Inventory Valuation + Unmoved Stock)'

    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    include_zero_stock = fields.Boolean(
        string="Include Zero Stock (Unmoved)",
        default=False,
        help="Include products with 0 stock in the Unmoved Stock section.",
    )
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company',
        'companies_combined_stock_report_rel',
        'combined_stock_report_id',
        'company_id',
        string="Companies",
        default=lambda self: self.env.company,
    )

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()

    @api.model
    def default_get(self, fields_list):
        context = self._context
        res = super().default_get(fields_list)
        res.update({
            'company_ids': [(6, 0, context.get('allowed_company_ids', [self.env.company.id]))],
            'company_id': context.get('allowed_company_ids', [self.env.company.id])[0],
        })
        return res

    @api.constrains('from_date', 'to_date')
    def _check_date_range(self):
        for record in self:
            if record.to_date < record.from_date:
                raise ValidationError("To Date cannot be earlier than From Date.")

    # ─────────────────────────────────────────────────────────────
    #  Helper Methods
    # ─────────────────────────────────────────────────────────────
    def _get_excluded_category_ids(self):
        excluded_categs = self.env['product.category'].search([('exclude_from_stock_report', '=', True)])
        if not excluded_categs:
            return []
        return self.env['product.category'].search([('id', 'child_of', excluded_categs.ids)]).ids

    def _get_inventory_summary_type(self, categ):
        while categ:
            if categ.inventory_summary_type:
                return categ.inventory_summary_type
            name_upper = categ.name.upper() if categ.name else ''
            if name_upper == 'FG':
                return 'fg'
            elif name_upper == 'SFG':
                return 'sfg'
            elif name_upper in ('RAW MATERIALS', 'RM', 'RAW MATERIAL'):
                return 'rm'
            elif name_upper in ('PACKING MATERIALS', 'PM', 'PACKING MATERIAL', 'PM & CONSUMABLES'):
                return 'pm'
            categ = categ.parent_id
        return False

    # ─────────────────────────────────────────────────────────────
    #  Inventory Valuation data (replicates inventory_valuation.py)
    # ─────────────────────────────────────────────────────────────
    def _prepare_inventory_valuation_data(self, excluded_only=False):
        import pytz
        user_tz = pytz.timezone(self.env.user.tz or self.env.context.get('tz') or 'Asia/Kolkata')
        local_from = user_tz.localize(datetime.combine(self.from_date, datetime.min.time()))
        local_to = user_tz.localize(datetime.combine(self.to_date, datetime.max.time()))
        formatted_from_date = local_from.astimezone(pytz.utc).replace(tzinfo=None)
        formatted_to_date = local_to.astimezone(pytz.utc).replace(tzinfo=None)

        excluded_categ_ids = self._get_excluded_category_ids()

        domain = [
            ('state', '=', 'done'),
            ('date', '>=', formatted_from_date),
            ('date', '<=', formatted_to_date),
            ('is_inventory', '=', True),
            ('company_id', 'in', self.company_ids.ids),
        ]
        if excluded_categ_ids:
            if excluded_only:
                domain.append(('product_id.categ_id', 'in', excluded_categ_ids))
            else:
                domain.append(('product_id.categ_id', 'not in', excluded_categ_ids))
        elif excluded_only:
            return {}

        inventory_move_lines = self.env['stock.move.line'].search(domain)

        # Initialise containers regardless of whether moves exist in range
        # (PM carry-forward may still add rows even when the range has no moves)
        company_report_data = defaultdict(list)
        utc_tz = pytz.utc
        ist_tz = pytz.timezone('Asia/Kolkata')

        # ── Helper: build one row dict from a stock.move.line ──────────────
        def _row_from_move(move, use_quant_for_book=True):
            phys = move.inventory_quntaity      # snapshot from inventory adjustment

            # Determine signed qty based on move direction (mirrors Odoo UI colour):
            #   inventory → internal : GREEN  → stock ADDED   → +qty_done
            #   internal  → inventory: RED    → stock REMOVED → -qty_done
            if move.location_id.usage == 'inventory' and move.location_dest_id.usage == 'internal':
                signed_qty = move.qty_done
            elif move.location_id.usage == 'internal' and move.location_dest_id.usage == 'inventory':
                signed_qty = -move.qty_done
            else:
                signed_qty = move.qty_done

            if use_quant_for_book:
                # Book Stock = previous on-hand BEFORE this inventory adjustment.
                # current_on_hand (stock.quant) already reflects the adjustment, so
                # we subtract signed_qty to recover what was on-hand before the count.
                # Fallback: if previous would be negative (first-time / no history),
                # use current on-hand as the displayed book stock.
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '=', False),
                    ('company_id', '=', move.company_id.id or self.company_id.id),
                ])
                current_on_hand = sum(quants.mapped('quantity'))
                previous_on_hand = current_on_hand - signed_qty
                book = previous_on_hand if previous_on_hand >= 0 else current_on_hand
            else:
                # Carry-forward moves: derive pre-adjustment book stock from move
                # direction so we reflect the historical state, not current stock.quant.
                book = phys - signed_qty

            # Variance = Physical − Book  (negative when physical < book stock)
            v_qty = phys - book

            m_date = move.date
            if not m_date.tzinfo:
                m_date = utc_tz.localize(m_date)
            m_date_ist = m_date.astimezone(ist_tz).replace(tzinfo=None)


            return {
                'product_id': move.product_id.id,
                'date': m_date_ist,
                'name': move.product_id.display_name,
                'on_hand_qty_at_date': move.previous_on_hand_qty,
                'physical_qty': move.inventory_quntaity,
                'signed_qty': signed_qty,
                'variance_qty': move.inventory_quntaity + move.previous_on_hand_qty if move.previous_on_hand_qty <= 0 else move.inventory_quntaity - move.previous_on_hand_qty,
                'from_location': move.location_id.display_name if move.location_id else '',
                'to_location': move.location_dest_id.display_name if move.location_dest_id else '',
                'product_category': move.product_id.categ_id.display_name if move.product_id.categ_id else '',
                'inventory_summary_type': self._get_inventory_summary_type(move.product_id.categ_id),
                'uom_id': move.product_id.uom_id.name if move.product_id.uom_id else '',
                'sales_price': move.product_id.list_price or 0.0,
            }
        # ───────────────────────────────────────────────────────────────────

        # ── Main loop: inventory moves within the requested date range ─────
        for move in inventory_move_lines:
            company_name = move.company_id.name or self.company_id.name
            # use_quant_for_book=True (default): stock.quant is current & accurate
            company_report_data[company_name].append(_row_from_move(move))

        # ── PM Carry-Forward Logic ─────────────────────────────────────────
        # For Packing Materials (PM) products, always show the most recent
        # inventory adjustment even if it falls BEFORE the report's from_date.
        # The last-known physical stock count is carried forward until a newer
        # adjustment is recorded (e.g. adjustment on 10-Mar shows in 11-Mar,
        # 12-Mar, … reports until the next adjustment overrides it).
        for company in self.company_ids:
            company_name = company.name

            # PM product IDs already covered by the current date range
            pm_covered = {
                d['product_id']
                for d in company_report_data.get(company_name, [])
                if d.get('inventory_summary_type') == 'pm'
            }

            # All inventory adjustments BEFORE this report's from_date
            past_domain = [
                ('state', '=', 'done'),
                ('date', '<', formatted_from_date),
                ('is_inventory', '=', True),
                ('company_id', '=', company.id),
            ]
            if excluded_categ_ids:
                if excluded_only:
                    past_domain.append(('product_id.categ_id', 'in', excluded_categ_ids))
                else:
                    past_domain.append(('product_id.categ_id', 'not in', excluded_categ_ids))
            elif excluded_only:
                continue

            # Ordered newest-first so the first hit per product = most recent
            past_moves = self.env['stock.move.line'].search(
                past_domain, order='date desc'
            )

            seen_pm = set()
            for move in past_moves:
                pid = move.product_id.id
                if self._get_inventory_summary_type(move.product_id.categ_id) != 'pm':
                    continue            # carry-forward applies to PM only
                if pid in pm_covered:
                    continue            # already in report from current range
                if pid in seen_pm:
                    continue            # already picked the latest for this product
                seen_pm.add(pid)
                # use_quant_for_book=False: derive historical book from move direction
                # because stock.quant reflects TODAY (may be 0 after consumption)
                company_report_data[company_name].append(
                    _row_from_move(move, use_quant_for_book=False)
                )
        # ───────────────────────────────────────────────────────────────────

        if not any(company_report_data.values()):
            return {}

        for company_name, data_list in company_report_data.items():
            data_list.sort(key=lambda x: (x['date'], x['name']))

        return dict(company_report_data)

    # ─────────────────────────────────────────────────────────────
    #  Unmoved Stock data (replicates unmoved_stock_report.py)
    # ─────────────────────────────────────────────────────────────
    def _prepare_unmoved_stock_data(self, excluded_only=False):
        import pytz
        user_tz = pytz.timezone(self.env.user.tz or self.env.context.get('tz') or 'Asia/Kolkata')
        local_from = user_tz.localize(datetime.combine(self.from_date, datetime.min.time()))
        local_to = user_tz.localize(datetime.combine(self.to_date, datetime.max.time()))
        formatted_from_date = local_from.astimezone(pytz.utc).replace(tzinfo=None)
        formatted_to_date = local_to.astimezone(pytz.utc).replace(tzinfo=None)

        company_report_data = {}
        excluded_categ_ids = self._get_excluded_category_ids()

        for company in self.company_ids:
            adjusted_lines = self.env['stock.move.line'].search([
                ('state', '=', 'done'),
                ('date', '>=', formatted_from_date),
                ('date', '<=', formatted_to_date),
                ('is_inventory', '=', True),
                ('company_id', '=', company.id),
            ])
            adjusted_product_ids = adjusted_lines.mapped('product_id').ids

            domain = []
            if adjusted_product_ids:
                domain.append(('id', 'not in', adjusted_product_ids))
            if excluded_categ_ids:
                if excluded_only:
                    domain.append(('categ_id', 'in', excluded_categ_ids))
                else:
                    domain.append(('categ_id', 'not in', excluded_categ_ids))
            elif excluded_only:
                continue

            current_lang = self.env.context.get('lang') or 'en_US'
            unmoved_products = self.env['product.product'].with_context(
                lang=current_lang,
                to_date=formatted_to_date,
                company_id=company.id,
            ).search(domain)

            report_data = []
            for p in unmoved_products:
                stock_qty = p.qty_available
                if stock_qty <= 0 and not self.include_zero_stock:
                    continue

                product_category = p.categ_id.display_name if p.categ_id else ''
                uom_name = p.uom_id.display_name or p.uom_name if p.uom_id else ''
                sales_price = p.list_price if p.list_price else 0.0

                report_data.append({
                    'product_id': p.id,
                    'name': p.display_name,
                    'product_category': product_category,
                    'inventory_summary_type': self._get_inventory_summary_type(p.categ_id),
                    'uom_id': uom_name,
                    'sales_price': sales_price,
                    'on_hand_qty': stock_qty,
                    'on_hand_qty_at_date': stock_qty,
                    'physical_qty': 0.0,
                    'signed_qty': -stock_qty,
                })

            report_data.sort(key=lambda x: x['name'])

            if report_data:
                company_report_data[company.name] = report_data

        return company_report_data

    # ─────────────────────────────────────────────────────────────
    #  Excel generation
    # ─────────────────────────────────────────────────────────────
    def action_print_xlsx(self):
        inv_data = self._prepare_inventory_valuation_data()
        unmoved_data = self._prepare_unmoved_stock_data()
        
        excluded_inv_data = self._prepare_inventory_valuation_data(excluded_only=True)
        excluded_unmoved_data = self._prepare_unmoved_stock_data(excluded_only=True)

        # Collect all company names across both datasets
        all_companies = list(dict.fromkeys(
            list(inv_data.keys()) + list(unmoved_data.keys())
        ))
        
        excluded_companies = list(dict.fromkeys(
            list(excluded_inv_data.keys()) + list(excluded_unmoved_data.keys())
        ))

        if not all_companies and not excluded_companies:
            raise ValidationError(
                _("No data found for the selected date range and companies.\n"
                  "There are no inventory adjustment records and no unmoved stock products.")
            )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ── Shared formats ──────────────────────────────────────
        style_highlight = workbook.add_format({
            'bold': True, 'bg_color': '#E0E0E0',
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_highlight_left = workbook.add_format({
            'bold': True, 'bg_color': '#E0E0E0',
            'align': 'left', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_normal = workbook.add_format({
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_normal_left = workbook.add_format({
            'align': 'left', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_title = workbook.add_format({
            'bold': True, 'font_size': 12,
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_section = workbook.add_format({
            'bold': True, 'font_size': 11,
            'bg_color': '#4472C4', 'font_color': '#FFFFFF',
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd hh:mm:ss',
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_summary_label = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter',
        })
        style_summary_value = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter',
        })
        style_summary_pct = workbook.add_format({
            'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0%',
        })

        shared_headers = [
            "S.no", "Product name", "Product Category(parent)", "UOM", "Sales price",
            "Book Stock(On Hand Qty)", "Physical Stock(Counted Qty)", "Variance In Qty",
            "Book Stock Value", "Physical Stock Value", "Variance In Value", "Variance in(%)",
        ]
        shared_col_widths = [5, 40, 28, 10, 12, 20, 22, 15, 18, 20, 18, 15]

        # ══════════════════════════════════════════════════════
        #  CREATE SUMMARY SHEET
        # ══════════════════════════════════════════════════════
        summary_sheet = workbook.add_worksheet('Inventory Valuation Summary')
        
        # Merge Top Title
        summary_sheet.merge_range(0, 0, 0, 7, 'Inventory Valuation Summary', style_section)
        
        # Row 2: Dates
        summary_sheet.write(1, 1, "From", style_title)
        summary_sheet.write(1, 2, self.from_date.strftime('%d-%m-%Y'), style_normal)
        summary_sheet.write(1, 4, "TO", style_title)
        summary_sheet.write(1, 6, self.to_date.strftime('%d-%m-%Y'), style_normal)
        
        # Row 3: Headers
        summary_sheet.write(2, 0, "Outlet name", style_highlight)
        summary_sheet.write(2, 1, f"FG on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 2, f"SFG on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 3, f"RM on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 4, "TOTAL", style_highlight)
        summary_sheet.write(2, 5, "PM & Consumables", style_highlight)
        summary_sheet.write(2, 6, "GRAND TOTAL", style_highlight)
        summary_sheet.write(2, 7, "Declared Variance value", style_highlight)

        # Set summary column widths
        summary_sheet.set_column(0, 7, 20)
        
        summary_current_row = 3

        runs = [
            ('', all_companies, inv_data, unmoved_data),
            ('Excluded-', excluded_companies, excluded_inv_data, excluded_unmoved_data),
        ]

        # ══════════════════════════════════════════════════════════════════
        #  VALIDATION SHEETS  — Stock Variants & Excluded Stock Variants
        #  These sheets expose the product-level detail that feeds the
        #  Inventory Valuation Summary so the numbers can be cross-checked.
        # ══════════════════════════════════════════════════════════════════
        def _write_variants_sheet(sheet_title, datasets):
            """
            datasets: list of (company_name, inv_rows) tuples to consolidate.
            inv_rows is a list of dicts with keys: product_id, name,
            product_category, inventory_summary_type, uom_id, sales_price,
            physical_qty.
            """
            ws = workbook.add_worksheet(sheet_title[:31])

            # ── Column widths & headers ──────────────────────────────────
            var_headers = [
                "S.no", "Company", "Product Name", "Product Category",
                "Category Type", "UOM", "Sales Price",
                "Book Stock (On Hand Qty)", "Physical Stock (Counted Qty)", 
                "Variance In Qty", "Book Stock Value", "Physical Stock Value", 
                "Variance In Value", "Variance in(%)"
            ]
            var_col_widths = [5, 22, 40, 30, 12, 10, 12, 20, 22, 15, 18, 20, 18, 15]
            for i, w in enumerate(var_col_widths):
                ws.set_column(i, i, w)

            # Title row
            ws.merge_range(0, 0, 0, len(var_headers) - 1, sheet_title, style_section)
            # Date row
            ws.write(1, 1, "From", style_title)
            ws.write(1, 2, self.from_date.strftime('%d-%m-%Y'), style_normal)
            ws.write(1, 4, "To", style_title)
            ws.write(1, 5, self.to_date.strftime('%d-%m-%Y'), style_normal)
            # Header row
            for col, hdr in enumerate(var_headers):
                ws.write(2, col, hdr, style_highlight)
            ws.set_row(2, 30)

            current_row = 3
            sno = 1
            grand_totals = {'fg': 0.0, 'sfg': 0.0, 'rm': 0.0, 'pm': 0.0, 'other': 0.0}

            for company_name, inv_rows in datasets:
                for data in inv_rows:
                    phys = data.get('physical_qty', 0.0)
                    book = data.get('on_hand_qty_at_date', 0.0)
                    variance = data.get('signed_qty', 0.0)
                    price = data.get('sales_price', 0.0)
                    
                    val_phys = phys * price
                    val_book = book * price
                    val_var = variance * price
                    
                    var_pct = (variance / book * 100) if book != 0 else (100 if phys > 0 else 0)
                    
                    cat = data.get('inventory_summary_type') or 'other'
                    cat_label = {'fg': 'FG', 'sfg': 'SFG', 'rm': 'RM',
                                 'pm': 'PM', 'other': 'Other'}.get(cat, cat.upper())

                    ws.write(current_row, 0, sno, style_normal)
                    ws.write(current_row, 1, company_name, style_normal_left)
                    ws.write(current_row, 2, data.get('name', ''), style_normal_left)
                    ws.write(current_row, 3, data.get('product_category', ''), style_normal)
                    ws.write(current_row, 4, cat_label, style_normal)
                    ws.write(current_row, 5, data.get('uom_id', ''), style_normal)
                    ws.write(current_row, 6, "{:.2f}".format(price), style_normal)
                    ws.write(current_row, 7, "{:.2f}".format(book), style_normal)
                    ws.write(current_row, 8, "{:.2f}".format(phys), style_normal)
                    ws.write(current_row, 9, "{:.2f}".format(variance), style_normal)
                    ws.write(current_row, 10, "{:.2f}".format(val_book), style_normal)
                    ws.write(current_row, 11, "{:.2f}".format(val_phys), style_normal)
                    ws.write(current_row, 12, "{:.2f}".format(val_var), style_normal)
                    ws.write(current_row, 13, "{:.2f}".format(var_pct), style_normal)

                    grand_totals[cat if cat in grand_totals else 'other'] += val_phys
                    current_row += 1
                    sno += 1

            # ── Grand total rows by category ────────────────────────────
            current_row += 1  # blank separator
            cat_order = [('fg', 'FG Total'), ('sfg', 'SFG Total'),
                         ('rm', 'RM Total'), ('pm', 'PM & Consumables Total'),
                         ('other', 'Other Total')]
            overall = 0.0
            for cat_key, cat_label in cat_order:
                v = grand_totals[cat_key]
                if v == 0.0:
                    continue
                ws.merge_range(current_row, 0, current_row, 10, cat_label, style_highlight)
                ws.write(current_row, 11, "{:.2f}".format(v), style_highlight)
                overall += v
                current_row += 1

            ws.merge_range(current_row, 0, current_row, 10, 'GRAND TOTAL', style_section)
            ws.write(current_row, 11, "{:.2f}".format(overall), style_section)

        # Build datasets: group all companies' inv_data and unmoved_data rows
        regular_datasets = [
            (cn, inv_data.get(cn, []) + unmoved_data.get(cn, []))
            for cn in all_companies
        ]
        excluded_datasets = [
            (cn, excluded_inv_data.get(cn, []) + excluded_unmoved_data.get(cn, []))
            for cn in excluded_companies
        ]

        if regular_datasets:
            pass  # written after regular company sheets below
        if excluded_datasets:
            pass  # written after excluded company sheets below
        # ──────────────────────────────────────────────────────────────────

        # ── Sheet order ──────────────────────────────────────────────────
        # 1. Inventory Valuation Summary  (already created above)
        # 2. Stock Variance Report sheets (regular companies)
        # 3. Stock Variants               (validation detail)
        # 4. Excluded Stock Variance Report sheets
        # 5. Excluded Stock Variants      (validation detail)
        # ─────────────────────────────────────────────────────────────────

        # ── PASS 1: Regular company Stock Variance sheets ─────────────────
        for company_name in all_companies:
            company_inv = inv_data.get(company_name, [])
            company_unmoved = unmoved_data.get(company_name, [])

            # --- SUMMARY CALCULATION ---
            comp_fg = comp_sfg = comp_rm = comp_pm = comp_variance = 0.0

            for data in company_inv:
                comp_variance += (data['variance_qty'] * data['sales_price'])

                val = data['physical_qty'] * data['sales_price']
                book_val = data['on_hand_qty_at_date'] * data['sales_price']
                cat = data.get('inventory_summary_type')
                if cat == 'fg': comp_fg += val
                elif cat == 'sfg': comp_sfg += val
                elif cat == 'rm': comp_rm += val

            # Also add excluded PM products into the PM & Consumables summary column
            excluded_company_inv = excluded_inv_data.get(company_name, [])
            for data in excluded_company_inv:
                cat = data.get('inventory_summary_type')
                if cat == 'pm':
                    comp_pm += data['on_hand_qty_at_date'] * data['sales_price']

            # Add variance from unmoved stock (treated as -100% loss/variance)
            # Regular unmoved items
            for data in company_unmoved:
                val = (data['on_hand_qty'] * data['sales_price'])
                comp_variance -= val





            comp_total = comp_fg + comp_sfg + comp_rm
            comp_grand = comp_total + comp_pm


            summary_sheet.write(summary_current_row, 0, company_name, style_normal_left)
            summary_sheet.write(summary_current_row, 1, "{:.2f}".format(comp_fg), style_normal)
            summary_sheet.write(summary_current_row, 2, "{:.2f}".format(comp_sfg), style_normal)
            summary_sheet.write(summary_current_row, 3, "{:.2f}".format(comp_rm), style_normal)
            summary_sheet.write(summary_current_row, 4, "{:.2f}".format(comp_total), style_normal)
            summary_sheet.write(summary_current_row, 5, "{:.2f}".format(comp_pm), style_normal)
            summary_sheet.write(summary_current_row, 6, "{:.2f}".format(comp_grand), style_normal)
            summary_sheet.write(summary_current_row, 7, "{:.2f}".format(comp_variance or 0.0), style_normal)
            summary_current_row += 1
            # ---------------------------

            worksheet = workbook.add_worksheet(company_name[:31])

            for idx, width in enumerate(shared_col_widths):
                worksheet.set_column(idx, idx, width)

            current_row = 0

            # ── SECTION 1: INVENTORY VALUATION REPORT ─────────────────────
            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Stock Variance Report ({company_name})', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_inv:
                count = 1
                total_sales_price = total_book_stock = total_physical_stock = 0.0
                total_variance_qty = total_book_stock_value = 0.0
                total_physical_stock_value = total_variance_value = 0.0

                for data in company_inv:
                    book_stock = data['on_hand_qty_at_date']
                    # Physical Stock (Counted Qty) = previous_on_hand_qty - quantity
                    # Variance In Qty = quantity  (qty_done = the adjustment quantity)
                    # signed_qty: +ve for GREEN (stock added), -ve for RED (stock removed)
                    variance_in_qty = data['variance_qty']
                    # Physical Stock (Counted Qty) = inventory_quntaity snapshot
                    physical_stock = data.get('physical_qty', 0.0)
                    book_stock_value = book_stock * data['sales_price']
                    physical_stock_value = physical_stock * data['sales_price']
                    variance_in_value = variance_in_qty * data['sales_price']
                    variance_in_pct = (
                        (variance_in_qty / book_stock * 100) if book_stock != 0
                        else (100 if physical_stock > 0 else 0)
                    )
                    # print('book_stockbook_stock', book_stock)

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(book_stock), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_in_qty or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_stock_value), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_stock_value), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_in_value or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_in_pct), style_normal)

                    total_sales_price += data['sales_price']
                    total_book_stock += book_stock
                    total_physical_stock += physical_stock
                    total_variance_qty += variance_in_qty
                    total_book_stock_value += book_stock_value
                    total_physical_stock_value += physical_stock_value
                    total_variance_value += variance_in_value
                    current_row += 1
                    count += 1

                total_variance_pct = (
                    (total_variance_qty / total_book_stock * 100) if total_book_stock != 0
                    else (100 if total_physical_stock > 0 else 0)
                )

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(total_physical_stock), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(total_variance_qty or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(total_physical_stock_value), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(total_variance_value or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(total_variance_pct), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No inventory adjustment records found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── SECTION 2: UNMOVED STOCK REPORT ───────────────────────────
            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Unmoved Stock Report ({company_name})', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_unmoved:
                count = 1
                total_sales_price = total_book_stock = 0.0
                total_book_stock_value = 0.0

                for data in company_unmoved:
                    qty = data['on_hand_qty']
                    book_val = qty * data['sales_price']
                    # Products not moved/counted today:
                    # Physical Stock = 0, Variance = 0 - qty = negative book stock
                    physical_stock_u = 0.0
                    variance_u = -qty
                    physical_val_u = 0.0
                    variance_val_u = -book_val
                    variance_pct_u = -100.0 if qty > 0 else 0.0

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(qty), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock_u), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_u or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_val), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_val_u), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_val_u or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_pct_u), style_normal)

                    total_sales_price += data['sales_price']
                    total_book_stock += qty
                    total_book_stock_value += book_val
                    current_row += 1
                    count += 1

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(-total_book_stock or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(-total_book_stock_value or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(-100.0 if total_book_stock > 0 else 0.0), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No unmoved stock products found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── SECTION 3: SKU SUMMARY ─────────────────────────────────────
            unique_declared = len(set(d['name'] for d in company_inv))
            unique_unmoved = len(set(d['name'] for d in company_unmoved))
            total_skus = unique_declared + unique_unmoved
            declaration_pct = (unique_declared / total_skus) if total_skus > 0 else 0.0

            worksheet.write(current_row, 0, "Total no of SKU", style_summary_label)
            worksheet.write(current_row, 1, total_skus, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declared SKU", style_summary_label)
            worksheet.write(current_row, 1, unique_declared, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declaration %", style_summary_label)
            worksheet.write(current_row, 1, declaration_pct, style_summary_pct)
            current_row += 1

        # ── After PASS 1 → Stock Variants validation sheet ────────────────
        if regular_datasets:
            _write_variants_sheet('Stock Variants', regular_datasets)

        # ── PASS 2: Excluded company Stock Variance sheets ────────────────
        for company_name in excluded_companies:
            company_inv = excluded_inv_data.get(company_name, [])
            company_unmoved = excluded_unmoved_data.get(company_name, [])

            safe_sheet_name = f"Excluded-{company_name}"[:31]
            worksheet = workbook.add_worksheet(safe_sheet_name)

            for idx, width in enumerate(shared_col_widths):
                worksheet.set_column(idx, idx, width)

            current_row = 0

            # ── SECTION 1: INVENTORY VALUATION REPORT (EXCLUDED) ──────────
            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Stock Variance Report ({company_name}) - Excluded', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_inv:
                count = 1
                total_sales_price = total_book_stock = total_physical_stock = 0.0
                total_variance_qty = total_book_stock_value = 0.0
                total_physical_stock_value = total_variance_value = 0.0

                for data in company_inv:
                    book_stock = data['on_hand_qty_at_date']
                    # signed_qty: +ve for GREEN (stock added), -ve for RED (stock removed)
                    variance_in_qty = data['signed_qty']
                    # Physical Stock (Counted Qty) = inventory_quntaity snapshot
                    physical_stock = data.get('physical_qty', 0.0)
                    book_stock_value = book_stock * data['sales_price']
                    physical_stock_value = physical_stock * data['sales_price']
                    variance_in_value = variance_in_qty * data['sales_price']
                    variance_in_pct = (
                        (variance_in_qty / book_stock * 100) if book_stock != 0
                        else (100 if physical_stock > 0 else 0)
                    )

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(book_stock), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_in_qty or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_stock_value), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_stock_value), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_in_value or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_in_pct), style_normal)

                    total_sales_price += data['sales_price']
                    total_book_stock += book_stock
                    total_physical_stock += physical_stock
                    total_variance_qty += variance_in_qty
                    total_book_stock_value += book_stock_value
                    total_physical_stock_value += physical_stock_value
                    total_variance_value += variance_in_value
                    current_row += 1
                    count += 1

                total_variance_pct = (
                    (total_variance_qty / total_book_stock * 100) if total_book_stock != 0
                    else (100 if total_physical_stock > 0 else 0)
                )

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(total_physical_stock), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(total_variance_qty or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(total_physical_stock_value), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(total_variance_value or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(total_variance_pct), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No inventory adjustment records found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── SECTION 2: UNMOVED STOCK (EXCLUDED) ───────────────────────
            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Unmoved Stock Report ({company_name}) - Excluded', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_unmoved:
                count = 1
                total_sales_price = total_book_stock = 0.0
                total_book_stock_value = 0.0

                for data in company_unmoved:
                    qty = data['on_hand_qty']
                    book_val = qty * data['sales_price']
                    # Products not moved/counted today:
                    # Physical Stock = 0, Variance = 0 - qty = negative book stock
                    physical_stock_u = 0.0
                    variance_u = -qty
                    physical_val_u = 0.0
                    variance_val_u = -book_val
                    variance_pct_u = -100.0 if qty > 0 else 0.0

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(qty), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock_u), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_u or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_val), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_val_u), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_val_u or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_pct_u), style_normal)

                    total_sales_price += data['sales_price']
                    total_book_stock += qty
                    total_book_stock_value += book_val
                    current_row += 1
                    count += 1

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(-total_book_stock or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(-total_book_stock_value or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(-100.0 if total_book_stock > 0 else 0.0), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No unmoved stock products found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── SECTION 3: SKU SUMMARY (EXCLUDED) ─────────────────────────
            unique_declared = len(set(d['name'] for d in company_inv))
            unique_unmoved = len(set(d['name'] for d in company_unmoved))
            total_skus = unique_declared + unique_unmoved
            declaration_pct = (unique_declared / total_skus) if total_skus > 0 else 0.0

            worksheet.write(current_row, 0, "Total no of SKU", style_summary_label)
            worksheet.write(current_row, 1, total_skus, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declared SKU", style_summary_label)
            worksheet.write(current_row, 1, unique_declared, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declaration %", style_summary_label)
            worksheet.write(current_row, 1, declaration_pct, style_summary_pct)
            current_row += 1

        # ── After PASS 2 → Excluded Stock Variants validation sheet ──────
        if excluded_datasets:
            _write_variants_sheet('Excluded Stock Variants', excluded_datasets)

        workbook.close()
        xlsx_data = output.getvalue()
        output.close()
        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = (
            f"Combined_Stock_Report_"
            f"{self.from_date.strftime('%Y-%m-%d')}_to_{self.to_date.strftime('%Y-%m-%d')}.xlsx"
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    # ─────────────────────────────────────────────────────────────
    #  Email-only XLSX: only 2 sheets
    #  1. Inventory Valuation Summary
    #  2. Company-wise Stock Variance Report sheets
    #  (Excluded sheets, Stock Variants validation, Unmoved Stock
    #   sections are intentionally omitted from the daily email.)
    # ─────────────────────────────────────────────────────────────
    def _generate_email_xlsx(self):
        """
        Generate a minimal XLSX for the daily email cron job.
        Only two categories of sheets are produced:
          1. 'Inventory Valuation Summary'  – same summary table as the
             full manual report.
          2. Per-company 'Stock Variance Report' sheets – the inventory-
             adjustment detail for each company (no Excluded, no Unmoved
             Stock section, no Stock-Variants validation sheet).
        Returns raw bytes of the workbook.
        """
        inv_data = self._prepare_inventory_valuation_data()
        excluded_inv_data = self._prepare_inventory_valuation_data(excluded_only=True)

        all_companies = list(inv_data.keys())
        excluded_companies = list(excluded_inv_data.keys())

        # Merge company list for the summary (same logic as action_print_xlsx)
        summary_companies = list(dict.fromkeys(all_companies + excluded_companies))
        
        # Exclude specific companies from email report as requested
        excluded_email_companies = ['KARAIKAL IYANGARS FOODS LIMITED - PY', 'KIFL - TN']
        summary_companies = [c for c in summary_companies if c not in excluded_email_companies]
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ── Shared formats ──────────────────────────────────────
        style_highlight = workbook.add_format({
            'bold': True, 'bg_color': '#E0E0E0',
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_normal = workbook.add_format({
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_normal_left = workbook.add_format({
            'align': 'left', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_title = workbook.add_format({
            'bold': True, 'font_size': 12,
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })
        style_section = workbook.add_format({
            'bold': True, 'font_size': 11,
            'bg_color': '#4472C4', 'font_color': '#FFFFFF',
            'align': 'center', 'text_wrap': True, 'valign': 'vcenter',
        })

        shared_headers = [
            "S.no", "Product name", "Product Category(parent)", "UOM", "Sales price",
            "Book Stock(On Hand Qty)", "Physical Stock(Counted Qty)", "Variance In Qty",
            "Book Stock Value", "Physical Stock Value", "Variance In Value", "Variance in(%)",
        ]
        shared_col_widths = [5, 40, 28, 10, 12, 20, 22, 15, 18, 20, 18, 15]

        # ══════════════════════════════════════════════════════
        #  SHEET 1: Inventory Valuation Summary
        # ══════════════════════════════════════════════════════
        summary_sheet = workbook.add_worksheet('Inventory Valuation Summary')
        summary_sheet.merge_range(0, 0, 0, 7, 'Inventory Valuation Summary', style_section)
        summary_sheet.write(1, 1, "From", style_title)
        summary_sheet.write(1, 2, self.from_date.strftime('%d-%m-%Y'), style_normal)
        summary_sheet.write(1, 4, "TO", style_title)
        summary_sheet.write(1, 6, self.to_date.strftime('%d-%m-%Y'), style_normal)
        summary_sheet.write(2, 0, "Outlet name", style_highlight)
        summary_sheet.write(2, 1, f"FG on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 2, f"SFG on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 3, f"RM on {self.to_date.strftime('%d-%m-%Y')}", style_highlight)
        summary_sheet.write(2, 4, "TOTAL", style_highlight)
        summary_sheet.write(2, 5, "PM & Consumables", style_highlight)
        summary_sheet.write(2, 6, "GRAND TOTAL", style_highlight)
        summary_sheet.write(2, 7, "Declared Variance value", style_highlight)
        summary_sheet.set_column(0, 7, 20)
        summary_current_row = 3

        # Fetch unmoved stock data once for all companies
        unmoved_all = self._prepare_unmoved_stock_data()
        excluded_unmoved_all = self._prepare_unmoved_stock_data(excluded_only=True)

        # ══════════════════════════════════════════════════════
        #  SHEET 2+: Per-company Stock Variance Report sheets
        # ══════════════════════════════════════════════════════
        for company_name in summary_companies:
            company_inv = inv_data.get(company_name, [])
            company_unmoved = unmoved_all.get(company_name, [])

            # --- SUMMARY CALCULATION ---
            comp_fg = comp_sfg = comp_rm = comp_pm = comp_variance = 0.0

            for data in company_inv:
                comp_variance += (data['variance_qty'] * data['sales_price'])
                val = data['physical_qty'] * data['sales_price']
                book_val = data['on_hand_qty_at_date'] * data['sales_price']
                cat = data.get('inventory_summary_type')
                if cat == 'fg': comp_fg += val
                elif cat == 'sfg': comp_sfg += val
                elif cat == 'rm': comp_rm += val

            # Also add excluded PM products into the PM & Consumables summary column
            excluded_company_inv = excluded_inv_data.get(company_name, [])
            for data in excluded_company_inv:
                cat = data.get('inventory_summary_type')
                if cat == 'pm':
                    comp_pm += data['on_hand_qty_at_date'] * data['sales_price']

            # Add variance from unmoved stock (treated as -100% loss/variance)
            # Regular unmoved items
            for data in company_unmoved:
                val = (data['on_hand_qty'] * data['sales_price'])
                comp_variance -= val



            comp_total = comp_fg + comp_sfg + comp_rm
            comp_grand = comp_total + comp_pm

            summary_sheet.write(summary_current_row, 0, company_name, style_normal_left)
            summary_sheet.write(summary_current_row, 1, "{:.2f}".format(comp_fg), style_normal)
            summary_sheet.write(summary_current_row, 2, "{:.2f}".format(comp_sfg), style_normal)
            summary_sheet.write(summary_current_row, 3, "{:.2f}".format(comp_rm), style_normal)
            summary_sheet.write(summary_current_row, 4, "{:.2f}".format(comp_total), style_normal)
            summary_sheet.write(summary_current_row, 5, "{:.2f}".format(comp_pm), style_normal)
            summary_sheet.write(summary_current_row, 6, "{:.2f}".format(comp_grand), style_normal)
            summary_sheet.write(summary_current_row, 7, "{:.2f}".format(comp_variance or 0.0), style_normal)
            summary_current_row += 1

            # ── Company detail sheet ───────────────────────────
            worksheet = workbook.add_worksheet(company_name[:31])
            for idx, width in enumerate(shared_col_widths):
                worksheet.set_column(idx, idx, width)

            current_row = 0

            # Title
            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Stock Variance Report ({company_name})', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_inv:
                count = 1
                total_sales_price = total_book_stock = total_physical_stock = 0.0
                total_variance_qty = total_book_stock_value = 0.0
                total_physical_stock_value = total_variance_value = 0.0

                for data in company_inv:
                    book_stock = data['on_hand_qty_at_date']
                    # Physical Stock (Counted Qty) = previous_on_hand_qty - quantity
                    # Variance In Qty = quantity  (qty_done = the adjustment quantity)
                    # signed_qty: +ve for GREEN (stock added), -ve for RED (stock removed)
                    variance_in_qty = data['signed_qty']
                    # Physical Stock (Counted Qty) = inventory_quntaity snapshot
                    physical_stock = data.get('physical_qty', 0.0)
                    book_stock_value = book_stock * data['sales_price']
                    physical_stock_value = physical_stock * data['sales_price']
                    variance_in_value = variance_in_qty * data['sales_price']
                    variance_in_pct = (
                        (variance_in_qty / book_stock * 100) if book_stock != 0
                        else (100 if physical_stock > 0 else 0)
                    )

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(book_stock), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_in_qty or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_stock_value), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_stock_value), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_in_value or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_in_pct), style_normal)

                    total_sales_price += data['sales_price']
                    total_book_stock += book_stock
                    total_physical_stock += physical_stock
                    total_variance_qty += variance_in_qty
                    total_book_stock_value += book_stock_value
                    total_physical_stock_value += physical_stock_value
                    total_variance_value += variance_in_value
                    current_row += 1
                    count += 1

                total_variance_pct = (
                    (total_variance_qty / total_book_stock * 100) if total_book_stock != 0
                    else (100 if total_physical_stock > 0 else 0)
                )

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(total_physical_stock), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(total_variance_qty or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(total_physical_stock_value), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(total_variance_value or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(total_variance_pct), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No inventory adjustment records found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── UNMOVED STOCK SECTION ──────────────────────────
            company_unmoved = unmoved_all.get(company_name, [])

            worksheet.merge_range(
                current_row, 0, current_row, len(shared_headers) - 1,
                f'Unmoved Stock Report ({company_name})', style_section,
            )
            worksheet.set_row(current_row, 22)
            current_row += 1

            worksheet.write(current_row, 0, "From Date", style_title)
            worksheet.write(current_row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(current_row, 2, "To Date", style_title)
            worksheet.write(current_row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)
            current_row += 1

            for col_idx, header in enumerate(shared_headers):
                worksheet.write(current_row, col_idx, header, style_highlight)
            worksheet.set_row(current_row, 30)
            current_row += 1

            if company_unmoved:
                count = 1
                total_sales_price_u = total_book_stock_u = 0.0
                total_book_stock_value_u = 0.0

                for data in company_unmoved:
                    qty = data['on_hand_qty']
                    book_val_u = qty * data['sales_price']
                    # Products not moved/counted today:
                    # Physical Stock = 0, Variance = 0 - qty = negative book stock
                    physical_stock_u = 0.0
                    variance_u = -qty
                    physical_val_u = 0.0
                    variance_val_u = -book_val_u
                    variance_pct_u = -100.0 if qty > 0 else 0.0

                    worksheet.write(current_row, 0, count, style_normal)
                    worksheet.write(current_row, 1, data['name'], style_normal_left)
                    worksheet.write(current_row, 2, data['product_category'], style_normal)
                    worksheet.write(current_row, 3, data['uom_id'], style_normal)
                    worksheet.write(current_row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                    worksheet.write(current_row, 5, "{:.2f}".format(qty), style_normal)
                    worksheet.write(current_row, 6, "{:.2f}".format(physical_stock_u), style_normal)
                    worksheet.write(current_row, 7, "{:.2f}".format(variance_u or 0.0), style_normal)
                    worksheet.write(current_row, 8, "{:.2f}".format(book_val_u), style_normal)
                    worksheet.write(current_row, 9, "{:.2f}".format(physical_val_u), style_normal)
                    worksheet.write(current_row, 10, "{:.2f}".format(variance_val_u or 0.0), style_normal)
                    worksheet.write(current_row, 11, "{:.2f}".format(variance_pct_u), style_normal)

                    total_sales_price_u += data['sales_price']
                    total_book_stock_u += qty
                    total_book_stock_value_u += book_val_u
                    current_row += 1
                    count += 1

                worksheet.merge_range(current_row, 0, current_row, 3, 'Grand Total', style_highlight)
                worksheet.write(current_row, 4, "{:.2f}".format(total_sales_price_u), style_highlight)
                worksheet.write(current_row, 5, "{:.2f}".format(total_book_stock_u), style_highlight)
                worksheet.write(current_row, 6, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 7, "{:.2f}".format(-total_book_stock_u or 0.0), style_highlight)
                worksheet.write(current_row, 8, "{:.2f}".format(total_book_stock_value_u), style_highlight)
                worksheet.write(current_row, 9, "{:.2f}".format(0.0), style_highlight)
                worksheet.write(current_row, 10, "{:.2f}".format(-total_book_stock_value_u or 0.0), style_highlight)
                worksheet.write(current_row, 11, "{:.2f}".format(-100.0 if total_book_stock_u > 0 else 0.0), style_highlight)
                current_row += 1
            else:
                worksheet.merge_range(
                    current_row, 0, current_row, len(shared_headers) - 1,
                    'No unmoved stock products found for this period.', style_normal,
                )
                current_row += 1

            current_row += 2

            # ── SKU SUMMARY ────────────────────────────────────
            style_summary_label = workbook.add_format({
                'border': 1, 'align': 'left', 'valign': 'vcenter',
            })
            style_summary_value = workbook.add_format({
                'border': 1, 'align': 'right', 'valign': 'vcenter',
            })
            style_summary_pct = workbook.add_format({
                'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '0%',
            })

            unique_declared = len(set(d['name'] for d in company_inv))
            unique_unmoved = len(set(d['name'] for d in company_unmoved))
            total_skus = unique_declared + unique_unmoved
            declaration_pct = (unique_declared / total_skus) if total_skus > 0 else 0.0

            worksheet.write(current_row, 0, "Total no of SKU", style_summary_label)
            worksheet.write(current_row, 1, total_skus, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declared SKU", style_summary_label)
            worksheet.write(current_row, 1, unique_declared, style_summary_value)
            current_row += 1

            worksheet.write(current_row, 0, "Declaration %", style_summary_label)
            worksheet.write(current_row, 1, declaration_pct, style_summary_pct)
            current_row += 1

        workbook.close()
        return output.getvalue()
