# -*- coding: utf-8 -*-
from odoo import models,fields,api
from collections import defaultdict

from datetime import date, timedelta,datetime
from odoo.fields import Date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
import io
import xlsxwriter
import base64


class ProductVarianceReport(models.TransientModel):
    _name = 'product.variance.report'
    _description = 'Product Variance Report'

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char() 
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many('res.company', 'companies_product_variance_report_relation', 'product_variance_report_id', 'company_id', string="Companies",default=lambda self: self.env.company)
    from_date = fields.Date(string = 'From Date', required = True)
    to_date = fields.Date(string = 'To Date', required=True)
    
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
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Sheet1')

        # Define styles
        style_highlight = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})
        style_title = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})

        worksheet.merge_range('A1:N1', 'Stock Variance Report', style_title)
        row = 1
        col = 0
        worksheet.write(row, col, 'Company', style_highlight)
        col += 1
        for company in self.company_ids:
            worksheet.write(row, col, company.name, style_normal)
            col += 1

        col = 0
        row += 1
        date_from = self.from_date.strftime('%d-%m-%Y')
        date_to = self.to_date.strftime('%d-%m-%Y')

        worksheet.write(row, col, 'Date From', style_highlight)
        worksheet.write(row, col + 1, str(date_from), style_normal)
        worksheet.write(row, col + 2, 'To', style_highlight)
        worksheet.write(row, col + 3, str(date_to), style_normal)

        headers = [
            "S.No",
            "From Location",
            "To Loaction",
            "Product Name",
            "Product Category",
            "UOM",
            "Sales Price",
            "Variance In Qty",
            "Variance in Value",
        ]

        row += 2
        col = 0
        for header in headers:
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 18)
            col += 1
        count = 1

        stock_move_lines = self.env['stock.move.line'].search([
            ('state', '=', 'done'),
            ('is_inventory', '=', True),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date),
        ])

        product_data = defaultdict(lambda: {
            'from_locations': set(),
            'to_locations': set(),
            'category': '',
            'uom': '',
            'sales_price': 0.0,
            'quantity': 0.0
        })

        for line in stock_move_lines:
            product = line.product_id
            data = product_data[product]

            data['from_locations'].add(line.location_id.display_name)
            data['to_locations'].add(line.location_dest_id.display_name)
            data['category'] = product.categ_id.display_name
            data['uom'] = product.uom_id.display_name
            data['sales_price'] = product.lst_price
            data['quantity'] += line.quantity
        # Write to Excel
        row += 1
        for product, data in product_data.items():
            from_location = ', '.join(data['from_locations'])
            to_location = ', '.join(data['to_locations'])
            total_value = data['quantity'] * data['sales_price']


            worksheet.write(row, 0, count, style_normal)
            worksheet.write(row, 1, from_location, style_normal)
            worksheet.write(row, 2, to_location, style_normal)
            worksheet.write(row, 3, product.display_name, style_normal)
            worksheet.write(row, 4, data['category'], style_normal)
            worksheet.write(row, 5, data['uom'], style_normal)
            worksheet.write(row, 6, "{:.2f}".format(data['sales_price']), style_normal)
            worksheet.write(row, 7, "{:.2f}".format(data['quantity']), style_normal)  # Correct usage
            worksheet.write(row, 8, "{:.2f}".format(total_value), style_normal)  # New column for total = qty * price


            row += 1
            count += 1

        worksheet = workbook.add_worksheet('Sheet2')
        worksheet.merge_range('A1:N1', 'Stock Variance Report', style_title)
        row = 1
        col = 0
        worksheet.write(row, col, 'Company', style_highlight)
        col += 1
        for company in self.company_ids:
            worksheet.write(row, col, company.name, style_normal)
            col += 1

        col = 0
        row += 1
        date_from = self.from_date.strftime('%d-%m-%Y')
        date_to = self.to_date.strftime('%d-%m-%Y')

        worksheet.write(row, col, 'Date From', style_highlight)
        worksheet.write(row, col + 1, str(date_from), style_normal)
        worksheet.write(row, col + 2, 'To', style_highlight)
        worksheet.write(row, col + 3, str(date_to), style_normal)

        headers = [
            "S.No",
            "From Location",
            "To Loaction",
            "Product Name",
            "Product Category",
            "UOM",
            "Cost Price",
            "Variance In Qty",
            "Variance in Value",
        ]

        row += 2
        col = 0
        for header in headers:
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 18)
            col += 1
        count = 1

        stock_move_lines = self.env['stock.move.line'].search([
            ('state', '=', 'done'),
            ('is_inventory', '=', True),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date),
        ])

        product_data = defaultdict(lambda: {
            'from_locations': set(),
            'to_locations': set(),
            'category': '',
            'uom': '',
            'sales_price': 0.0,
            'quantity': 0.0
        })

        for line in stock_move_lines:
            product = line.product_id
            data = product_data[product]

            data['from_locations'].add(line.location_id.display_name)
            data['to_locations'].add(line.location_dest_id.display_name)
            data['category'] = product.categ_id.display_name
            data['uom'] = product.uom_id.display_name
            data['sales_price'] = product.standard_price
            data['quantity'] += line.quantity
        # Write to Excel
        row += 1
        for product, data in product_data.items():
            from_location = ', '.join(data['from_locations'])
            to_location = ', '.join(data['to_locations'])
            total_value = data['quantity'] * data['sales_price']


            worksheet.write(row, 0, count, style_normal)
            worksheet.write(row, 1, from_location, style_normal)
            worksheet.write(row, 2, to_location, style_normal)
            worksheet.write(row, 3, product.display_name, style_normal)
            worksheet.write(row, 4, data['category'], style_normal)
            worksheet.write(row, 5, data['uom'], style_normal)
            worksheet.write(row, 6, "{:.2f}".format(data['sales_price']), style_normal)
            worksheet.write(row, 7, "{:.2f}".format(data['quantity']), style_normal)  # Correct usage
            worksheet.write(row, 8, "{:.2f}".format(total_value), style_normal)  # New column for total = qty * price

            row += 1
            count += 1

        workbook.close()
        xlsx_data = output.getvalue()
        output.close()

        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = "stock_variance_report.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
