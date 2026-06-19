# -*- coding: utf-8 -*-
from odoo import models,fields,api,_
from collections import defaultdict
from odoo.exceptions import ValidationError
from datetime import date, timedelta,datetime
import io
import xlsxwriter
import base64


class InventoryValuationReport(models.TransientModel):
    _name = 'inventory.valuation.report'
    _description = 'Inventory Valuation Report'

    from_date = fields.Date(string = 'From Date', required = True)
    to_date = fields.Date(string = 'To Date', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company',
        'companies_inventory_valuation_report_rel',
        'inventory_valuation_report_id',
        'company_id',
        string="Companies",
        default=lambda self: self.env.company,
    )
    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()

    @api.model
    def default_get(self, fields):
        context = self._context
        res = super().default_get(fields)
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
   
    def _verify_data_exists(
            self,
            formatted_from_date,
            formatted_to_date
    ):
        inventory_move_lines = self.env['stock.move.line'].search([
            ('state', '=', 'done'),
            ('date', '>=', formatted_from_date),
            ('date', '<=', formatted_to_date),
            ('is_inventory', '=', True),
            ('company_id', 'in', self.company_ids.ids),
        ])
        
        if not inventory_move_lines:
            raise ValidationError(
                _("No inventory adjustments found for the selected date range.\n"
                  "From Date: %s\n"
                  "To Date: %s\n\n"
                  "Please select a date range that contains inventory adjustment records.") % 
                (self.from_date.strftime('%Y-%m-%d'), self.to_date.strftime('%Y-%m-%d'))
            )
        
        return inventory_move_lines

    def _prepare_report_data(self):
        # Local import or rely on standard imports. Ideally should be at top level but for minimal diff:
        import pytz
        
        formatted_from_date = datetime.combine(self.from_date, datetime.min.time())
        formatted_to_date = datetime.combine(self.to_date, datetime.max.time())

        inventory_move_lines = self._verify_data_exists(
            formatted_from_date,
            formatted_to_date
        )

        company_report_data = defaultdict(list)

        utc_tz = pytz.utc
        ist_tz = pytz.timezone('Asia/Kolkata')

        for move in inventory_move_lines:
            company_name = move.company_id.name or self.company_id.name
            # We want to know the stock situation at the EXACT time of this move.
            # 'qty_available' on a product context with 'to_date' gives the stock *including* moves up to that date/time.
            # So, if we set to_date = move.date, the resulting qty_available should be the "Physical Stock" (Post-Adjustment Stock).
            
            # Ensure we are looking at the specific company context
            product = move.product_id.with_context(
                to_date=move.date,
                allowed_company_ids=self.company_ids.ids,
                company_id=move.company_id.id or self.company_id.id
            )
            
            # This is the stock AFTER the move (Physical Stock / Counted Qty)
            physical_stock = product.qty_available

            # The adjustment quantity (Variance) is the quantity done in this move.
            # We need to determine the sign based on the move type (internal vs adjustment).
            # For inventory adjustments (is_inventory=True), usually:
            # - If location_id is 'Inventory adjustment' (virtual) and dest is 'Stock', it's an INCREASE (+).
            # - If location_id is 'Stock' and dest is 'Inventory adjustment', it's a DECREASE (-).
            
            variance_qty = 0.0
            if move.location_id.usage == 'inventory' and move.location_dest_id.usage == 'internal':
                variance_qty = move.qty_done # Incoming (Addition to stock)
            elif move.location_id.usage == 'internal' and move.location_dest_id.usage == 'inventory':
                variance_qty = -move.qty_done # Outgoing (Reduction from stock)
            else:
                # Fallback for unexpected moves, or internal transfers marked as inventory?
                # If it's just a move, let's trust the move logic or maybe it doesn't affect variance in the same way?
                # For safety in this report context, we assume standard adjustment moves.
                variance_qty = move.qty_done
                # If it is a purely internal move (internal->internal), variance might be 0 for the warehouse total, 
                # but this report seems to target adjustments. 
                # Let's stick to the standard adjustment logic.

            # "On Hand" (Book Stock) is the stock BEFORE this move happened.
            # On Hand + Variance = Physical Stock
            # So, On Hand = Physical Stock - Variance
            on_hand_qty = physical_stock - variance_qty

            product_category = move.product_id.categ_id.display_name if move.product_id.categ_id else ''
            uom_id = move.product_id.uom_id.name if move.product_id.uom_id else ''
            sales_price = move.product_id.list_price if move.product_id.list_price else 0.0

            # Locations
            from_location = move.location_id.display_name if move.location_id else ''
            to_location = move.location_dest_id.display_name if move.location_dest_id else ''

            # Convert move.date (UTC) to IST
            move_date_utc = move.date
            if not move_date_utc.tzinfo:
                move_date_utc = utc_tz.localize(move_date_utc)
            
            move_date_ist = move_date_utc.astimezone(ist_tz)
            # Remove timezone info for Excel writing (or keep it if format handles it, but naive datetime is safer usually)
            move_date_ist_naive = move_date_ist.replace(tzinfo=None)

            company_report_data[company_name].append({
                'date': move_date_ist_naive, # Use IST date (naive)
                'name': move.product_id.display_name,
                'on_hand_qty_at_date': on_hand_qty,
                'physical_qty': physical_stock,
                'variance_qty': variance_qty,
                'from_location': from_location,
                'to_location': to_location,
                'product_category': product_category,
                'uom_id': uom_id,
                'sales_price': sales_price,
            })
        
        # Sort by Date then Product Name
        for company_name, data_list in company_report_data.items():
            data_list.sort(key=lambda x: (x['date'], x['name']))

        return company_report_data

    def action_print_xlsx(self):
        company_report_data = self._prepare_report_data()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        style_highlight = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0', 'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})
        style_highlight_left = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0', 'align': 'left', 'text_wrap': True, 'valign': 'vcenter'})
        style_normal = workbook.add_format({'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})
        style_normal_left = workbook.add_format({'align': 'left', 'text_wrap': True, 'valign': 'vcenter'})
        style_title = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})
        # Updated date format to include time
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss', 'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})

        headers = [
            "S.no",
            "Date", # Added Date column
            'From Location',
            'To Location',
            "Product name",
            "Product Category(parent)",
            "UOM",
            "Sales price",
            "Book Stock(On Hand Qty)",
            "Physical Stock(Counted Qty)",
            "Variance In Qty",
            "Book Stock Value",
            "Physical Stock Value",
            "Variance In Value",
            "Variance in(%)"
        ]

        for company_name, report_data in company_report_data.items():
            safe_sheet_name = company_name[:31]
            worksheet = workbook.add_worksheet(safe_sheet_name)
            
            row = 1
            col = 0
            worksheet.merge_range(f'A{row}:O{row}', f'Stock Variance Report ({company_name})', style_highlight) # Extended range to O
            row += 1
            worksheet.write(row, 0, "From Date", style_title)
            worksheet.write(row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(row, 3, "To Date", style_title)
            worksheet.write(row, 4, self.to_date.strftime('%Y-%m-%d'), style_normal)

            row += 1
            col = 0
            column_widths = [
                5,   # S.no
                20,  # Date (Increased width for time)
                25,  # From Location
                25,  # To Location
                40,  # Product name
                28,  # Product Category(parent)
                10,  # UOM
                12,  # Sales price
                20,  # Book Stock(On Hand Qty)
                22,  # Physical Stock(Counted Qty)
                15,  # Variance In Qty
                18,  # Book Stock Value
                20,  # Physical Stock Value
                18,  # Variance In Value
                15,  # Variance in(%)
            ]
            
            for header in headers:
                worksheet.write(row, col, header, style_highlight)
                if col < len(column_widths):
                    worksheet.set_column(col, col, column_widths[col])
                col += 1
            
            worksheet.set_row(row, 30)

            row += 1
            count = 1

            # Initialize totals
            total_sales_price = 0.0
            total_book_stock = 0.0
            total_physical_stock = 0.0
            total_variance_qty = 0.0
            total_book_stock_value = 0.0
            total_physical_stock_value = 0.0
            total_variance_value = 0.0

            for data in report_data:
                book_stock = data['on_hand_qty_at_date']
                physical_stock = data['physical_qty']
                variance_in_qty = data['variance_qty']
                book_stock_value = book_stock * data['sales_price']
                physical_stock_value = physical_stock * data['sales_price']
                variance_in_value = variance_in_qty * data['sales_price']

                variance_in_percentage = (variance_in_qty / book_stock * 100) if book_stock != 0 else (100 if physical_stock > 0 else 0)

                worksheet.write(row, 0, count, style_normal)
                worksheet.write(row, 1, data['date'], date_format) # Write Date with Time
                worksheet.write(row, 2, data['from_location'], style_normal_left)
                worksheet.write(row, 3, data['to_location'], style_normal_left)
                worksheet.write(row, 4, data['name'], style_normal_left)
                worksheet.write(row, 5, data['product_category'], style_normal)
                worksheet.write(row, 6, data['uom_id'], style_normal)
                worksheet.write(row, 7, "{:.2f}".format(data['sales_price']), style_normal)
                worksheet.write(row, 8, "{:.2f}".format(book_stock), style_normal)
                worksheet.write(row, 9, "{:.2f}".format(physical_stock), style_normal)
                worksheet.write(row, 10, "{:.2f}".format(variance_in_qty), style_normal)
                worksheet.write(row, 11, "{:.2f}".format(book_stock_value), style_normal)
                worksheet.write(row, 12, "{:.2f}".format(physical_stock_value), style_normal)
                worksheet.write(row, 13, "{:.2f}".format(variance_in_value), style_normal)
                worksheet.write(row, 14, "{:.2f}".format(variance_in_percentage), style_normal)

                row += 1
                count += 1

                # Accumulate totals
                total_sales_price += data['sales_price']
                total_book_stock += book_stock
                total_physical_stock += physical_stock
                total_variance_qty += variance_in_qty
                total_book_stock_value += book_stock_value
                total_physical_stock_value += physical_stock_value
                total_variance_value += variance_in_value

            # Calculate total variance percentage
            total_variance_percentage = (total_variance_qty / total_book_stock * 100) if total_book_stock != 0 else (100 if total_physical_stock > 0 else 0)

            # Write Total Row
            worksheet.merge_range(row, 0, row, 6, 'Grand Total', style_highlight)
            worksheet.write(row, 7, "{:.2f}".format(total_sales_price), style_highlight)
            worksheet.write(row, 8, "{:.2f}".format(total_book_stock), style_highlight)
            worksheet.write(row, 9, "{:.2f}".format(total_physical_stock), style_highlight)
            worksheet.write(row, 10, "{:.2f}".format(total_variance_qty), style_highlight)
            worksheet.write(row, 11, "{:.2f}".format(total_book_stock_value), style_highlight)
            worksheet.write(row, 12, "{:.2f}".format(total_physical_stock_value), style_highlight)
            worksheet.write(row, 13, "{:.2f}".format(total_variance_value), style_highlight)
            worksheet.write(row, 14, "{:.2f}".format(total_variance_percentage), style_highlight)

        workbook.close()
        xlsx_data = output.getvalue()
        output.close()
        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = f"Inventory_Valuation_{self.from_date.strftime('%Y-%m-%d')}_to_{self.to_date.strftime('%Y-%m-%d')}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.model
    def send_daily_inventory_valuation_report(self):
        """
        Cron job method to generate the Inventory Valuation Report and email it
        to the Director (main company configuration).
        Skips emailing if there were no moves that day.
        """
        companies_with_mail = self.env['res.company'].search([('daily_reports_mail_id', '!=', False)])
        if not companies_with_mail:
            return  # No one to send the report to

        today_date = fields.Date.context_today(self)
        
        # We want to pull ALL companies for this one combined report
        all_companies = self.env['res.company'].search([])
        
        # Check if there are any valid stock moves for the day before generating.
        # This mirrors the behavior of _verify_data_exists but fails quietly for the cron logic
        formatted_today = datetime.combine(today_date, datetime.min.time())
        formatted_today_end = datetime.combine(today_date, datetime.max.time())
        
        stock_move_lines = self.env['stock.move.line'].search([
            ('state', '=', 'done'),
            ('date', '>=', formatted_today),
            ('date', '<=', formatted_today_end),
            ('is_inventory', '=', True),
            ('company_id', 'in', all_companies.ids),
        ], limit=1)
        
        if not stock_move_lines:
            # We don't send emails on days without moves!
            return

        # Use combined.stock.report._generate_email_xlsx() which produces
        # ONLY the 2 required sheets for the daily email:
        #   1. Inventory Valuation Summary
        #   2. Per-company Stock Variance Report sheets
        # (Excluded, Unmoved Stock, and Stock Variants validation sheets are
        #  intentionally omitted — they appear only in the manual print.)
        wizard = self.env['combined.stock.report'].create({
            'from_date': today_date,
            'to_date': today_date,
            'company_ids': [(6, 0, all_companies.ids)],
        })

        try:
            xlsx_data = wizard._generate_email_xlsx()
        except (ValidationError, Exception):
            return

        today_str = today_date.strftime('%Y-%m-%d')
        report_name = f"Daily_Inventory_Valuation_Report_{today_str}.xlsx"

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': report_name,
            'type': 'binary',
            'datas': base64.encodebytes(xlsx_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Send email to each configured company director
        for company in companies_with_mail:
            # Skip specified companies from receiving the email
            if company.name in ['KARAIKAL IYANGARS FOODS LIMITED - PY', 'KIFL - TN']:
                continue
            
            # Handle comma separated emails natively by cleaning up spaces
            recipients = ','.join([email.strip() for email in company.daily_reports_mail_id.split(',') if email.strip()])

            mail_values = {
                'subject': f"Daily Inventory Valuation Report - {today_str}",
                'body_html': f"<p>Dear Director ({company.name}),</p><p>Please find attached the Inventory Valuation Report for {today_str}. This report contains all daily physical stock adjustment movements.</p>",
                'email_to': recipients,
                'attachment_ids': [(4, attachment.id)],
            }
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()