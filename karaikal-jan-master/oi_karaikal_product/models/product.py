from odoo import api, fields, models
from datetime import date
import io
import base64
import xlwt

class ProductProduct(models.Model):
    _inherit = 'product.product'

    different = fields.Float(string="Differents", compute="_compute_different", store=True)

    @api.depends('qty_available')
    def _compute_different(self):
        StockMoveLine = self.env['stock.move.line']
        current_date = date.today()

        for product in self:
            stock_move_lines = StockMoveLine.search([
                ('product_id', '=', product.id),
                ('date', '>=', current_date.strftime('%Y-%m-%d 00:00:00')),
                ('date', '<=', current_date.strftime('%Y-%m-%d 23:59:59'))
            ])

            product.different = sum(stock_move_lines.mapped('quantity')) if stock_move_lines else 0


    def reset_different_field(self):
       
        self.search([]).write({'different': 0})

    
        
    def send_product_report(self):
        
        products = self.search([])

       
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Product Stock Report')

       
        headers = [
            "Product", "Unit Cost", "Total Value", "On Hand",
            "Different", "Free To Use", "Incoming", "Outgoing", "UoM"
        ]

       
        header_style = xlwt.easyxf('font: bold on; align: horiz center')
        for col_num, header in enumerate(headers):
            sheet.write(0, col_num, header, header_style)
            sheet.col(col_num).width = 5000  

        
        row_index = 1
        for product in products:
            sheet.write(row_index, 0, product.display_name)
            sheet.write(row_index, 1, product.avg_cost)
            sheet.write(row_index, 2, product.total_value)
            sheet.write(row_index, 3, product.qty_available)
            sheet.write(row_index, 4, product.different)
            sheet.write(row_index, 5, product.free_qty)
            sheet.write(row_index, 6, product.incoming_qty)
            sheet.write(row_index, 7, product.outgoing_qty)
            sheet.write(row_index, 8, product.uom_id.name)
            row_index += 1

        
        output = io.BytesIO()
        workbook.save(output)
        xls_data = output.getvalue()
        encoded_xls = base64.b64encode(xls_data)

        
        mail_values = {
            'subject': 'Daily Product Stock Report',
            'body_html': '<p>Please find attached the daily product stock report in XLS format.</p>',
            'email_to': 'akatheesan@karaikaliyangars.com',
            'attachment_ids': [(0, 0, {
                'name': 'product_stock_report.xls',
                'datas': encoded_xls,
                'mimetype': 'application/vnd.ms-excel'
            })],
        }

        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
