# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta, datetime
import io
import xlsxwriter
import base64

class UnmovedStockReport(models.TransientModel):
    _name = 'unmoved.stock.report'
    _description = 'Unmoved Stock Report'

    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    include_zero_stock = fields.Boolean(string="Include Zero Stock", default=False, help="Include products that had 0 stock during this period.")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company',
        'companies_unmoved_stock_report_rel',
        'unmoved_stock_report_id',
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
   
    def _prepare_report_data(self):
        # We find products that did NOT have an inventory adjustment between these dates.
        formatted_from_date = datetime.combine(self.from_date, datetime.min.time())
        formatted_to_date = datetime.combine(self.to_date, datetime.max.time())

        company_report_data = {}

        for company in self.company_ids:
            # Products that were adjusted (inventory moves) for THIS company
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

            # We also only want products that have some stock for THIS company
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
                    # Skip items with 0 stock unless the user explicitly wants to see them
                    continue

                product_category = p.categ_id.display_name if p.categ_id else ''
                # Use display_name and fallback to uom_name to ensure correct text representation
                uom_name = p.uom_id.display_name or p.uom_name if p.uom_id else ''
                sales_price = p.list_price if p.list_price else 0.0

                report_data.append({
                    'name': p.display_name,
                    'product_category': product_category,
                    'uom_id': uom_name,
                    'sales_price': sales_price,
                    'on_hand_qty': stock_qty,
                })
            
            # Sort by Product Name
            report_data.sort(key=lambda x: x['name'])
            
            if report_data:
                company_report_data[company.name] = report_data

        if not company_report_data:
            raise ValidationError("No unmoved products found for the selected date range and companies. Try checking 'Include Zero Stock'.")

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

        headers = [
            "S.no",
            "Product name",
            "Product Category(parent)",
            "UOM",
            "Sales price",
            "On Hand Qty",
            "Stock Value",
        ]

        # Loop through each company and create a dedicated worksheet
        for company_name, report_data in company_report_data.items():
            # Excel limits sheet names to 31 chars safely
            safe_sheet_name = company_name[:31] 
            worksheet = workbook.add_worksheet(safe_sheet_name)

            row = 1
            col = 0
            worksheet.merge_range(f'A{row}:G{row}', f'Unmoved Stock Report ({company_name})', style_highlight)
            row += 1
            worksheet.write(row, 0, "From Date", style_title)
            worksheet.write(row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
            worksheet.write(row, 2, "To Date", style_title)
            worksheet.write(row, 3, self.to_date.strftime('%Y-%m-%d'), style_normal)

            row += 1
            col = 0
            column_widths = [
                5,   # S.no
                40,  # Product name
                28,  # Product Category(parent)
                10,  # UOM
                12,  # Sales price
                20,  # On Hand Qty
                18,  # Stock Value
            ]
            
            for header in headers:
                worksheet.write(row, col, header, style_highlight)
                if col < len(column_widths):
                    worksheet.set_column(col, col, column_widths[col])
                col += 1
            
            worksheet.set_row(row, 30)

            row += 1
            count = 1

            total_sales_price = 0.0
            total_qty = 0.0
            total_value = 0.0

            for data in report_data:
                qty = data['on_hand_qty']
                val = qty * data['sales_price']

                worksheet.write(row, 0, count, style_normal)
                worksheet.write(row, 1, data['name'], style_normal_left)
                worksheet.write(row, 2, data['product_category'], style_normal)
                worksheet.write(row, 3, data['uom_id'], style_normal)
                worksheet.write(row, 4, "{:.2f}".format(data['sales_price']), style_normal)
                worksheet.write(row, 5, "{:.2f}".format(qty), style_normal)
                worksheet.write(row, 6, "{:.2f}".format(val), style_normal)

                row += 1
                count += 1

                total_sales_price += data['sales_price']
                total_qty += qty
                total_value += val

            # Write Total Row
            worksheet.merge_range(row, 0, row, 3, 'Grand Total', style_highlight)
            worksheet.write(row, 4, "{:.2f}".format(total_sales_price), style_highlight)
            worksheet.write(row, 5, "{:.2f}".format(total_qty), style_highlight)
            worksheet.write(row, 6, "{:.2f}".format(total_value), style_highlight)

        workbook.close()
        xlsx_data = output.getvalue()
        output.close()
        self.xls_file = base64.encodebytes(xlsx_data)
        
        # Dynamic filename based on selected dates
        file_date_suffix = f"{self.from_date.strftime('%Y-%m-%d')}_to_{self.to_date.strftime('%Y-%m-%d')}"
        self.xls_filename = f"Unmoved_Stock_{file_date_suffix}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.model
    def send_daily_unmoved_stock_report(self):
        """
        Cron job method to generate the Unmoved Stock Report and email it
        to the Director (main company configuration with 'unmoved_stock_mail_id').
        """
        # Find companies configured to receive this report (typically the Head Company)
        companies_with_mail = self.env['res.company'].search([('daily_reports_mail_id', '!=', False)])
        if not companies_with_mail:
            return  # No one to send the report to

        today_date = fields.Date.context_today(self)
        
        # We want to pull ALL companies for this one combined report
        all_companies = self.env['res.company'].search([])
        
        # Force language context to avoid missing translations in cron
        wizard = self.with_context(lang='en_US').create({
            'from_date': today_date,
            'to_date': today_date,
            'include_zero_stock': True,
            'company_ids': [(6, 0, all_companies.ids)],
        })
        
        try:
            # We don't want to raise ValidationError if there are no products, just catch it and maybe send an empty report or no email.
            wizard.action_print_xlsx()
        except ValidationError:
            return

        report_binary = wizard.xls_file
        today_str = today_date.strftime('%Y-%m-%d')
        report_name = f"Unmoved_Stock_{today_str}_to_{today_str}.xlsx"

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': report_name,
            'type': 'binary',
            'datas': report_binary,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Send email to each configured company director
        for company in companies_with_mail:
            # Handle comma separated emails natively by cleaning up spaces
            recipients = ','.join([email.strip() for email in company.daily_reports_mail_id.split(',') if email.strip()])
            
            mail_values = {
                'subject': f"Daily Unmoved Stock Report - {today_str}",
                'body_html': f"<p>Dear Director ({company.name}),</p><p>Please find attached the Unmoved Stock Report for {today_str}. This report includes products with zero stock across your companies.</p>",
                'email_to': recipients,
                'attachment_ids': [(4, attachment.id)],
            }
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
