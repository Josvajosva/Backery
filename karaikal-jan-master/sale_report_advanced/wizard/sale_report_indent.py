from odoo import models, fields
from datetime import datetime, timedelta
from io import BytesIO
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer
from odoo.exceptions import ValidationError
from reportlab.lib.styles import ParagraphStyle
import xlsxwriter

DATE_FORMAT = "%Y-%m-%d"

class SaleReportIndent(models.TransientModel):
    _name = "sale.report.indent"
    _description = "Sale Report Indent"
    
    customer_id = fields.Many2many('res.partner', string="Customer")
    product_category_id = fields.Many2many('product.category', string="Product Category")
    from_date = fields.Date(string = 'From Date', required = True,default=fields.Date.context_today)
    to_date = fields.Date(string = 'To Date', required=True,default=fields.Date.context_today)

    def _get_indent_data(self):
        if not self.customer_id:
            raise ValidationError("Please select a customer before generating the report.")
        if not self.product_category_id:
            raise ValidationError("Please select at least one product category before generating the report.")

        customer_names = list(self.customer_id.mapped('name'))[:20]
        data_dict = {}

       
        stock_pickings = self.env['stock.picking'].search([
            ('picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['assigned', 'confirmed']),
            ('scheduled_date', '>=', self.from_date),
            ('scheduled_date', '<=', self.to_date),
            ('partner_id', 'in', self.customer_id.ids),
            ('move_ids_without_package.product_id.categ_id', 'in', self.product_category_id.ids)])

        
        for picking in stock_pickings:            
            for line in picking.move_ids_without_package:
                if line.product_id.categ_id.id not in self.product_category_id.ids:
                    continue

                category_name = line.product_id.categ_id.name
                product_name = line.product_id.name
                customer_name = picking.partner_id.name
                qty = line.product_uom_qty or 0

                if category_name not in data_dict:
                    data_dict[category_name] = {}

                if product_name not in data_dict[category_name]:
                    data_dict[category_name][product_name] = {name: 0 for name in customer_names}

                data_dict[category_name][product_name][customer_name] += qty

        return data_dict, customer_names

    def action_get_indent_report(self):
        data_dict, customer_names = self._get_indent_data()

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        styles = getSampleStyleSheet()
        title = Paragraph("Indent Report", styles['Title'])

        elements = [title]

        customer_style = ParagraphStyle(
            'CustomerStyle',
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            alignment=1,  
            wordWrap=True
        )

        for category, products in data_dict.items():
            category_title = Paragraph(f"Category: {category}", styles['Heading2'])
            elements.append(category_title)

            header = ["SL. NO.", "Product Name"] + [Paragraph(name, customer_style) for name in customer_names] + ["Total"]
            data = [header]

            sl_no = 1
            for product_name, customer_data in products.items():
                row = [
                    sl_no,
                    Paragraph(product_name, customer_style),  
                ]
                total_qty = 0
                for customer in customer_names:
                    qty = customer_data.get(customer, 0)
                    row.append(f"{qty} qty" if qty else "-")
                    total_qty += qty
                row.append(f"{total_qty} qty" if total_qty else "-")
                data.append(row)
                sl_no += 1

            table = Table(data, colWidths=[30, 100] + [60 for _ in customer_names] + [60])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            elements.append(table)
            elements.append(Spacer(1, 12))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'Indent Report.pdf',
            'datas': base64.b64encode(pdf_data),
            'res_model': 'sale.report.indent',
            'res_id': self.id,
            'type': 'binary',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_get_indent_xls_report(self):
        data_dict, customer_names = self._get_indent_data()

        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Indent Report')

        header_format = workbook.add_format({
            'bold': True, 
            'align': 'center', 
            'valign': 'vcenter', 
            'bg_color': '#D3D3D3', 
            'border': 1
        })
        cell_format = workbook.add_format({
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter'
        })

        headers = ["SL. NO.", "Product Name"] + customer_names + ["Total"]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        row = 1
        sl_no = 1

        for category, products in data_dict.items():
            worksheet.merge_range(row, 0, row, len(headers) - 1, f"Category: {category}", header_format)
            row += 1

            for product_name, customer_data in products.items():
                worksheet.write(row, 0, sl_no, cell_format)
                worksheet.write(row, 1, product_name, cell_format)

                total_qty = 0
                col = 2
                for customer in customer_names:
                    qty = customer_data.get(customer, 0)
                    worksheet.write(row, col, qty if qty else '-', cell_format)
                    total_qty += qty
                    col += 1

                worksheet.write(row, col, total_qty if total_qty else '-', cell_format)
                row += 1
                sl_no += 1

        workbook.close()

        xls_data = buffer.getvalue()
        buffer.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'Indent Report.xlsx',
            'datas': base64.b64encode(xls_data),
            'res_model': 'sale.report.indent',
            'res_id': self.id,
            'type': 'binary',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }