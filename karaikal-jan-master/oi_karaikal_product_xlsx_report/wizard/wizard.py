# -*- coding: utf-8 -*-
from odoo import models,fields,api
import io
import xlsxwriter
import base64
from datetime import datetime, time, timedelta
from odoo.exceptions import UserError



class ProductDeliveryStatus(models.TransientModel):
    _name = 'product.delivery.status'
    _description = 'sales orders against delivery status day wise'

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()
    from_date = fields.Date(string = 'From Date', required = True)
    to_date = fields.Date(string = 'To Date', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many('res.company', 'companies_product_delivery_status_relation', 'product_delivery_status_id', 'company_id', string="Companies",default=lambda self: self.env.company)
    product_category_ids = fields.Many2many('product.category',string="Product Category",required = True)

    @api.model
    def default_get(self, fields):
        context = self._context
        res = super().default_get(fields)
        res.update({
                'company_ids': [(6,0, context['allowed_company_ids'])],
                'company_id': context['allowed_company_ids'][0],
            })
        return res

    def action_print_xlsx(self):
        if self.to_date < self.from_date:
            raise UserError("To Date must be greater than or equal to From Date.")
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Delivery Status Day Wise')

        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})
        style_normal_1 = workbook.add_format({'align': 'center', 'bold': True})
        merge_formatb = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#FFFFFF',
            'text_wrap': True
        })
        merge_formatb.set_font_size(9)

        headers = [
            "S.No",
            "Product Name",
            "Product Category",
            "Parent Category",
            "Indent Qty",
            "Issued Qty",
            "Delivery Address",
            "Outlet Name",
            "Product Mrp",
            "Value",
            "Percentage Achieved(%)",
        ]

        row = 1
        col = 0

        # Report Title
        worksheet.merge_range(f'A{row}:K{row}', 'Delivery Performance Report', merge_formatb)

        # From Date and To Date
        row += 1
        worksheet.write(row, 0, "From Date", style_normal_1)
        worksheet.write(row, 1, self.from_date.strftime('%Y-%m-%d'), style_normal)
        worksheet.write(row, 3, "To Date", style_normal_1)
        worksheet.write(row, 4, self.to_date.strftime('%Y-%m-%d'), style_normal)

        
        row += 2

        # Headers
        col = 0
        for header in headers:
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 14)
            col += 1

        row += 1
        count = 1
        total_value = 0

        from_datetime = datetime.combine(self.from_date, time.min) - timedelta(hours=5, minutes=30)
        to_datetime = datetime.combine(self.to_date, time.max) - timedelta(hours=5, minutes=30)

        # Get all relevant pickings
        pickings = self.env['stock.picking'].search([
            ('scheduled_date', '>=', from_datetime),
            ('scheduled_date', '<=', to_datetime),
            ('picking_type_id.code', '=', 'outgoing'),
            ('move_ids_without_package.product_id.categ_id', 'in', self.product_category_ids.ids),
        ])

        # Aggregate data by (product, customer)
        product_data = {}

        for picking in pickings:
            for move in picking.move_ids_without_package:
                if move.product_id.categ_id.id not in self.product_category_ids.ids:
                    continue

                product = move.product_id
                category = product.categ_id.name
                parent_category = product.categ_id.display_name
                partner = move.picking_id.partner_id
                key = (product.id, partner.id)  

                if key not in product_data:
                    product_data[key] = {
                        'product_name': product.name,
                        'product_category': category,
                        'parent_category':parent_category,
                        'indent_qty': 0.0,
                        'issued_qty': 0.0,
                        'company': picking.company_id.name,
                        'product_price': product.list_price,
                        'delivery_address': partner.name if partner else '',
                    }

                product_data[key]['indent_qty'] += move.product_uom_qty

                if picking.state == 'done':
                    product_data[key]['issued_qty'] += move.quantity

        # Write data to XLSX
        for data in product_data.values():
            indent_qty = data['indent_qty']
            issued_qty = data['issued_qty']
            product_price = data['product_price']
            value = issued_qty * product_price
            total_value += value
            percentage_achieved = (issued_qty / indent_qty * 100) if indent_qty else 0.0

            col = 0
            worksheet.write(row, col, count, style_normal)
            worksheet.write(row, col + 1, data['product_name'], style_normal)
            worksheet.write(row, col + 2, data['product_category'], style_normal)
            worksheet.write(row, col + 3, data['parent_category'], style_normal)
            worksheet.write(row, col + 4, indent_qty, style_normal)
            worksheet.write(row, col + 5, issued_qty, style_normal)
            worksheet.write(row, col + 6, data['delivery_address'] or "", style_normal)
            worksheet.write(row, col + 7, data['company'], style_normal)
            worksheet.write(row, col + 8, product_price, style_normal)
            worksheet.write(row, col + 9, value, style_normal)
            worksheet.write(row, col + 10, f"{percentage_achieved:.2f}%", style_normal)

            row += 1
            count += 1

        # Summary
        worksheet.write(row + 1, 8, "Category consolidate value", style_normal_1)
        worksheet.write(row + 1, 9, total_value, style_normal_1)

        worksheet2 = workbook.add_worksheet('Stock Transfer Analysis')

        style_title = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter'})
        style_label = workbook.add_format({'bold': True, 'align': 'left'})
        style_value = workbook.add_format({'align': 'left'})
        style_header = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#E6E6FA', 'border': 1})
        style_cell = workbook.add_format({'align': 'center', 'border': 1})
        style_bold_cell = workbook.add_format({'bold': True, 'align': 'center', 'border': 1})

        worksheet2.merge_range('A1:K1', 'Stock Transfer Analysis', style_title)

        # Extract unique delivery addresses
        delivery_addresses = sorted(set(data['delivery_address'] for data in product_data.values() if data['delivery_address']))
        address_col_map = {}

        col = 1
        worksheet2.write(3, 0, 'PARTICULARS', style_header)
        for address in delivery_addresses:
            worksheet2.merge_range(2, col, 2, col + 1, address, style_header)
            worksheet2.write(3, col, 'QTY', style_header)
            worksheet2.write(3, col + 1, 'PERCENTAGE', style_header)
            address_col_map[address] = (col, col + 1)
            col += 2

        worksheet2.set_column(0, 0, 45)
        for i in range(1, col):
            worksheet2.set_column(i, i, 14)

        def format_percentage(qty, total):
            if not total:
                return ''
            val = (qty / total) * 100
            return f"{val:.2f}%" if val != 0 else ''

        analysis_rows = [
            'Total Number of Indented Items',
            'Items Not Transferred but Indent Raised',
            'Items Transferred Without an Indent',
            'Items Transferred at 1% to 49% of Indent Items',
            'Items Transferred Between 50% and 89% of Indent Items',
            'Items Transferred Between 90% and 100% of Indent Items',
            'Items Transferred Above 100% of Indent Items',
            # 'Items Transferred Between 50% and 120% of Indent Items',
            # 'Items Transferred Above 121% of Indent Items',
            'Total Number of Items Transferred Against Indents',
            'Total Value of Items Transferred'
        ]

        row_index = 4

        for row_title in analysis_rows:
            worksheet2.write(row_index, 0, row_title, style_label)

            for address in delivery_addresses:
                indent_items = [
                    d for k, d in product_data.items() if d['delivery_address'] == address
                ]

                qty = ''
                percentage = ''

                if row_title == 'Total Number of Indented Items':
                    qty = sum(1 for d in indent_items if d['indent_qty'] > 0)

                elif row_title == 'Items Not Transferred but Indent Raised':
                    qty = sum(1 for d in indent_items if d['indent_qty'] > 0 and d['issued_qty'] == 0)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    percentage = format_percentage(qty, total)

                elif row_title == 'Items Transferred Without an Indent':
                    qty = sum(1 for d in indent_items if d['indent_qty'] == 0 and d['issued_qty'] > 0)

                elif row_title == 'Items Transferred at 1% to 49% of Indent Items':
                    qty = sum(1 for d in indent_items if d['indent_qty'] and 1 <= (d['issued_qty'] / d['indent_qty'] * 100) <= 49)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    # percentage = format_percentage(qty, total)

                elif row_title == 'Items Transferred Between 50% and 89% of Indent Items':
                    qty = sum(1 for d in indent_items if d['indent_qty'] and 50 <= (d['issued_qty'] / d['indent_qty'] * 100) <= 89)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    percentage = format_percentage(qty, total)

                elif row_title == 'Items Transferred Between 90% and 100% of Indent Items':
                    qty = sum(1 for d in indent_items if d['indent_qty'] and 90 <= (d['issued_qty'] / d['indent_qty'] * 100) <= 100)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    percentage = format_percentage(qty, total)

                elif row_title == 'Items Transferred Above 100% of Indent Items':
                    qty = sum(1 for d in indent_items if d['indent_qty'] and (d['issued_qty'] / d['indent_qty'] * 100) > 100)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    percentage = format_percentage(qty, total)

                elif row_title == 'Total Number of Items Transferred Against Indents':
                    qty = sum(1 for d in indent_items if d['indent_qty'] > 0 and d['issued_qty'] > 0)
                    total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                    percentage = format_percentage(qty, total)

                elif row_title == 'Total Value of Items Transferred':
                    qty = sum(d['issued_qty'] * d['product_price'] for d in indent_items if d['indent_qty'] > 0 and d['issued_qty'] > 0)

                col_qty, col_percent = address_col_map[address]

                # Apply bold style only to two specific rows
                is_bold_row = row_title in [
                    'Total Number of Items Transferred Against Indents',
                    'Total Value of Items Transferred'
                ]
                cell_style = style_bold_cell if is_bold_row else style_cell

                worksheet2.write(row_index, col_qty, qty, cell_style)
                worksheet2.write(row_index, col_percent, percentage, cell_style)

            row_index += 1

        # Finalize
        workbook.close()
        xlsx_data = output.getvalue()
        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = f"Delivery Performance Report {self.from_date.strftime('%Y-%m-%d')} to {self.to_date.strftime('%Y-%m-%d')}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
    


                # elif row_title == 'Items Transferred Between 50% and 120% of Indent Items':
                #     qty = sum(1 for d in indent_items if d['indent_qty'] and 50 <= (d['issued_qty'] / d['indent_qty'] * 100) <= 120)
                #     total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                #     percentage = format_percentage(qty, total)

                # elif row_title == 'Items Transferred Above 121% of Indent Items':
                #     qty = sum(1 for d in indent_items if d['indent_qty'] and (d['issued_qty'] / d['indent_qty'] * 100) > 120)
                #     total = sum(1 for d in indent_items if d['indent_qty'] > 0)
                #     percentage = format_percentage(qty, total)

                # elif row_title == 'Total Number of Items Transferred Against Indents':
                #     total_indented = sum(1 for d in indent_items if d['indent_qty'] > 0)
                #     not_transferred = sum(1 for d in indent_items if d['indent_qty'] > 0 and d['issued_qty'] == 0)
                #     low_transfer = sum(1 for d in indent_items if d['indent_qty'] and 1 <= (d['issued_qty'] / d['indent_qty'] * 100) <= 49)
                #     qty = total_indented - (not_transferred + low_transfer)
                #     percentage = format_percentage(qty, total_indented)

                # elif row_title == 'Total Value of Items Transferred':
                #     qty = sum(d['issued_qty'] * d['product_price'] for d in indent_items)