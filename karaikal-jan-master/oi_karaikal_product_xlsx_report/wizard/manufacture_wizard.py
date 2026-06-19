# -*- coding: utf-8 -*-
from odoo import models,fields,api
from datetime import date, timedelta,datetime
from odoo.fields import Date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
import io
import xlsxwriter
import base64


class DailyProductProductionReport(models.TransientModel):
    _name = 'daily.product.production.report'
    _description = 'Manufacturing daily product production plan excel report'

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char() 
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many('res.company', 'companies_daily_product_production_report_relation', 'daily_product_production_report_id', 'company_id', string="Companies",default=lambda self: self.env.company)
   
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
        worksheet = workbook.add_worksheet('Product Production')

        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})
        style_title = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})

        current_datetime = datetime.now().strftime('%d-%m-%Y')
        worksheet.merge_range('A1:K1', f'Product Production Report - {current_datetime}', style_title)

        headers = [
            "Product Name", "Product Category", "Product UOM", "Demand", 
            "On Hand", "Maximum Reorder", "Minimum Reorder", 
            "Confirmed", "In Progress", "Total to Produce", "Batch"
        ]

        row = 2
        col = 0

        for header in headers:
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 14)
            col += 1
        row += 1

        current_date = datetime.today().date()
        tomorrow_date = current_date + timedelta(days=1)

        stock_pickings = self.env['stock.picking'].search([
            ('picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['assigned', 'confirmed']),
            '|',
            ('scheduled_date', '<', tomorrow_date.strftime(DATE_FORMAT)),  # Records before tomorrow
            '&',
            ('scheduled_date', '>=', tomorrow_date.strftime(DATE_FORMAT)),  # Records for tomorrow
            ('scheduled_date', '<', (tomorrow_date + timedelta(days=1)).strftime(DATE_FORMAT)),
        ])

        product_data = {}

        # Collect data from stock pickings
        for picking in stock_pickings:
            for move in picking.move_ids_without_package:
                product = move.product_id

                if product.id not in product_data:
                    product_data[product.id] = {
                        'name': product.name or '',
                        'category': product.categ_id.display_name or '',
                        'uom': product.uom_id.name or '',
                        'demand': 0,
                        'on_hand': product.qty_available or 0,
                        'reorder_max': product.reordering_max_qty or 0,
                        'reorder_min': product.reordering_min_qty or 0,
                        'confirmed': 0,
                        'in_progress': 0,
                        'batch': sum(self.env['mrp.bom'].search([
    ('product_tmpl_id', '=', product.product_tmpl_id.id)
]).mapped('product_qty')) or 0  

                    }

                product_data[product.id]['demand'] += move.product_uom_qty

        # Collect data from mrp.production
        mrp_productions = self.env['mrp.production'].search([
            ('state', 'in', ['confirmed', 'progress'])
        ])

        for mo in mrp_productions:
            product = mo.product_id
            if product.id in product_data:
                if mo.state == 'confirmed':
                    product_data[product.id]['confirmed'] += mo.product_qty
                elif mo.state == 'progress':
                    product_data[product.id]['in_progress'] += mo.product_qty

        # Writing data to the XLSX file
        for product in product_data.values():
            col = 0
            worksheet.write(row, col, product['name'], style_normal)
            col += 1
            worksheet.write(row, col, product['category'], style_normal)
            col += 1
            worksheet.write(row, col, product['uom'], style_normal)
            col += 1
            worksheet.write(row, col, product['demand'], style_normal)
            col += 1
            worksheet.write(row, col, product['on_hand'], style_normal)
            col += 1
            worksheet.write(row, col, product['reorder_max'], style_normal)
            col += 1
            worksheet.write(row, col, product['reorder_min'], style_normal)
            col += 1
            worksheet.write(row, col, product['confirmed'], style_normal)
            col += 1
            worksheet.write(row, col, product['in_progress'], style_normal)
            col += 1

            total_to_produce = max(0, product['demand'] - product['on_hand'] + product['reorder_max'] - (product['confirmed'] + product['in_progress']))
            worksheet.write(row, col, total_to_produce, style_normal)
            col += 1

            worksheet.write(row, col, product['batch'], style_normal) 

            row += 1

        workbook.close()
        xlsx_data = output.getvalue()
        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = "daily_product_production_report.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
   
   
   
   
   
   
   
   
   