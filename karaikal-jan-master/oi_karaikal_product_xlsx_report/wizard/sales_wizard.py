# -*- coding: utf-8 -*-
from odoo import models, fields, api
import io
import xlsxwriter
import base64
from odoo.exceptions import ValidationError


class SaleCustomerCategory(models.TransientModel):
    _name = 'sale.customer.category'
    _description = 'Sales Report'

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company',
        'companies_sale_customer_category_relation',
        'sale_customer_category_id',
        'company_id',
        string="Companies",
        default=lambda self: self.env.company
    )
    is_inter_company = fields.Boolean(string="Without Inter-Company?", default=False)
    is_tax_excluded = fields.Boolean(
        string="Tax Excluded?",
        default=False
    )

    @api.model
    def default_get(self, fields):
        context = self._context
        res = super().default_get(fields)
        res.update({
            'company_ids': [(6, 0, context['allowed_company_ids'])],
            'company_id': context['allowed_company_ids'][0],
        })
        return res

    def action_print_xlsx(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Sales Report')

        # === Styles ===
        style_header = workbook.add_format({
            'bold': True, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter'
        })
        style_cell = workbook.add_format({
            'bold': 1, 'border': 1, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FFFFFF', 'text_wrap': True
        })
        style_cell.set_font_size(9)

        # === Headers ===
        headers = [
            "Outlet Name",
            "PARTICULARS",
            "Walk-in Customers (POS)",
            "Sale Order (MTO)",
            "Corporate Bulk Orders",
            "Custom Cakes",
            "Wholesale Supply",
            "Webstore Sales",
            "Food Aggregators",
            "Total Sales"
        ]
        row = 0
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_header)
            worksheet.set_column(col, col, 20)
        row += 1

        total_per_category = {
            'walk_in_customers': 0.0,
            'sale_order_mto': 0.0,
            'corporate_orders': 0.0,
            'custom_cakes': 0.0,
            'wholesale_supply': 0.0,
            'webstore_sales': 0.0,
            'food_aggregators': 0.0,
        }

        for company in self.company_ids:

            # Local totals per company (for correct last column)
            local_totals = {
                'walk_in_customers': 0.0,
                'sale_order_mto': 0.0,
                'corporate_orders': 0.0,
                'custom_cakes': 0.0,
                'wholesale_supply': 0.0,
                'webstore_sales': 0.0,
                'food_aggregators': 0.0,
            }

            pos_orders = self.env['pos.order'].search([
                ('date_order', '>=', self.from_date),
                ('date_order', '<=', self.to_date),
                ('company_id', '=', company.id),
            ])

            invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', self.from_date),
                ('invoice_date', '<=', self.to_date),
                ('company_id', '=', company.id),
            ])

            sale_orders = invoices.mapped('invoice_line_ids.sale_line_ids.order_id').filtered(
                lambda so: so.state == 'sale'
            )
            if self.is_inter_company:
                sale_orders = sale_orders.filtered(
                    lambda sale: True not in sale.partner_id.category_id.mapped('is_inter_company')
                     and not sale.partner_id.property_account_position_id.is_inter_company
                )

                pos_orders = pos_orders.filtered(
                    lambda pos: True not in pos.partner_id.category_id.mapped('is_inter_company')
                     and not pos.partner_id.property_account_position_id.is_inter_company
                )

            end_row = row + 2
            worksheet.merge_range(row, 0, end_row, 0, company.name or '', style_cell)

            particulars = ['TOTAL SALES', 'BILL COUNT', 'ATV']
            for idx, label in enumerate(particulars):
                worksheet.write(row + idx, 1, label, style_cell)


            pos_count = len(pos_orders)
            if not self.is_tax_excluded:
                pos_total = sum(pos_orders.mapped('amount_total'))
            else:
                pos_total = sum(pos_orders.mapped('amount_total')) - sum(pos_orders.mapped('amount_tax'))
            pos_atv = pos_total / pos_count if pos_count else 0

            worksheet.write(row, 2, "{:.2f}".format(pos_total), style_cell)
            worksheet.write(row + 1, 2, pos_count, style_cell)
            worksheet.write(row + 2, 2, "{:.2f}".format(pos_atv), style_cell)
            total_per_category['walk_in_customers'] += pos_total
            local_totals['walk_in_customers'] = pos_total

            def write_sales_category(col_index, sales_type_key):
                filtered = [s for s in sale_orders if s.sales_types == sales_type_key]
                invs = invoices.filtered(lambda inv: any(
                    so in filtered for so in inv.invoice_line_ids.sale_line_ids.order_id
                ))
                count = len(invs)

                vals = {
                    True: 'amount_untaxed',
                    False: 'amount_total'
                }
                total = sum(invs.mapped(vals[self.is_tax_excluded]))
                atv = total / count if count else 0

                worksheet.write(row, col_index, "{:.2f}".format(total), style_cell)
                worksheet.write(row + 1, col_index, count, style_cell)
                worksheet.write(row + 2, col_index, "{:.2f}".format(atv), style_cell)
                total_per_category[sales_type_key] += total
                local_totals[sales_type_key] = total

            write_sales_category(3, 'sale_order_mto')
            write_sales_category(4, 'corporate_orders')
            write_sales_category(5, 'custom_cakes')
            write_sales_category(6, 'wholesale_supply')
            write_sales_category(7, 'webstore_sales')
            write_sales_category(8, 'food_aggregators')

            company_total = sum(local_totals.values())

            worksheet.merge_range(row, 9, end_row, 9, "{:.2f}".format(company_total), style_cell)

            row = end_row + 2

        worksheet.write(row, 1, 'Total Sales by Category', style_header)
        worksheet.write(row, 2, "{:.2f}".format(total_per_category['walk_in_customers']), style_cell)
        worksheet.write(row, 3, "{:.2f}".format(total_per_category['sale_order_mto']), style_cell)
        worksheet.write(row, 4, "{:.2f}".format(total_per_category['corporate_orders']), style_cell)
        worksheet.write(row, 5, "{:.2f}".format(total_per_category['custom_cakes']), style_cell)
        worksheet.write(row, 6, "{:.2f}".format(total_per_category['wholesale_supply']), style_cell)
        worksheet.write(row, 7, "{:.2f}".format(total_per_category['webstore_sales']), style_cell)
        worksheet.write(row, 8, "{:.2f}".format(total_per_category['food_aggregators']), style_cell)

        final_total = sum(total_per_category.values())
        worksheet.write(row, 9, "{:.2f}".format(final_total), style_cell)

        workbook.close()
        xlsx_data = output.getvalue()

        filename = "sales_report_%s_to_%s.xlsx" % (
            self.from_date.strftime("%d-%m-%Y"),
            self.to_date.strftime("%d-%m-%Y"),
        )

        self.write({
            'xls_file': base64.encodebytes(xlsx_data),
            'xls_filename': filename,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

# from odoo import models,fields,api
# import io
# import xlsxwriter
# import base64


# class SaleCustomerCategory(models.TransientModel):
#     _name = 'sale.customer.category'
#     _description = 'Sales Report'

#     xls_file = fields.Binary(string="XLS file")
#     xls_filename = fields.Char()
#     from_date = fields.Date(string = 'From Date', required = True)
#     to_date = fields.Date(string = 'To Date', required=True)
#     company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
#     company_ids = fields.Many2many('res.company', 'companies_sale_customer_category_relation', 'sale_customer_category_id', 'company_id', string="Companies",default=lambda self: self.env.company)

#     @api.model
#     def default_get(self, fields):
#         context = self._context
#         res = super().default_get(fields)
#         res.update({
#                 'company_ids': [(6,0, context['allowed_company_ids'])],
#                 'company_id': context['allowed_company_ids'][0],
#             })
#         return res

#     def action_print_xlsx(self):
#         output = io.BytesIO()
#         workbook = xlsxwriter.Workbook(output, {'in_memory': True})
#         worksheet = workbook.add_worksheet('Sales Report')

#         # === Styles ===
#         style_header = workbook.add_format({
#             'bold': True, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter'
#         })
#         style_cell = workbook.add_format({
#             'bold': 1, 'border': 1, 'align': 'center', 'valign': 'vcenter',
#             'bg_color': '#FFFFFF', 'text_wrap': True
#         })
#         style_cell.set_font_size(9)

#         # === Headers ===
#         headers = [
#             "Outlet Name",
#             "PARTICULARS",
#             "Walk-in Customers (POS)",
#             "Sale Order (MTO)",
#             "Corporate Bulk Orders",
#             "Custom Cakes",
#             "Wholesale Supply",
#             "Webstore Sales",
#             "Food Aggregators",
#             "Total Sales"
#         ]
#         row = 0
#         for col, header in enumerate(headers):
#             worksheet.write(row, col, header, style_header)
#             worksheet.set_column(col, col, 20)
#         row += 1

#         total_per_category = {
#             'walk_in_customers': 0.0,
#             'sale_order_mto': 0.0,
#             'corporate_orders': 0.0,
#             'custom_cakes': 0.0,
#             'wholesale_supply': 0.0,
#             'webstore_sales': 0.0,
#             'food_aggregators': 0.0,
#         }

#         for company in self.company_ids:
#             pos_orders = self.env['pos.order'].search([
#                 ('date_order', '>=', self.from_date),
#                 ('date_order', '<=', self.to_date),
#                 ('company_id', '=', company.id),
#             ])

#             invoices = self.env['account.move'].search([
#                 ('move_type', '=', 'out_invoice'),
#                 ('state', '=', 'posted'),
#                 ('invoice_date', '>=', self.from_date),
#                 ('invoice_date', '<=', self.to_date),
#                 ('company_id', '=', company.id),
#             ])

#             sale_orders = invoices.mapped('invoice_line_ids.sale_line_ids.order_id').filtered(
#                 lambda so: so.state == 'sale'
#             )

#             end_row = row + 2
#             worksheet.merge_range(row, 0, end_row, 0, company.name or '', style_cell)

#             particulars = ['TOTAL SALES', 'BILL COUNT', 'ATV']
#             for idx, label in enumerate(particulars):
#                 worksheet.write(row + idx, 1, label, style_cell)

#             pos_count = len(pos_orders)
#             pos_total = sum(pos_orders.mapped('amount_total'))
#             pos_atv = pos_total / pos_count if pos_count else 0

#             worksheet.write(row, 2, "{:.2f}".format(pos_total), style_cell)
#             worksheet.write(row + 1, 2, pos_count, style_cell)
#             worksheet.write(row + 2, 2, "{:.2f}".format(pos_atv), style_cell)
#             total_per_category['walk_in_customers'] += pos_total

#             def write_sales_category(col_index, sales_type_key):
#                 filtered = [s for s in sale_orders if s.sales_types == sales_type_key]
#                 # we should calculate total from invoices, not order_id.amount_total
#                 invs = invoices.filtered(lambda inv: any(
#                     so in filtered for so in inv.invoice_line_ids.sale_line_ids.order_id
#                 ))
#                 count = len(invs)
#                 total = sum(invs.mapped('amount_total'))
#                 atv = total / count if count else 0

#                 worksheet.write(row, col_index, "{:.2f}".format(total), style_cell)
#                 worksheet.write(row + 1, col_index, count, style_cell)
#                 worksheet.write(row + 2, col_index, "{:.2f}".format(atv), style_cell)
#                 total_per_category[sales_type_key] += total

#             write_sales_category(3, 'sale_order_mto')
#             write_sales_category(4, 'corporate_orders')
#             write_sales_category(5, 'custom_cakes')
#             write_sales_category(6, 'wholesale_supply')
#             write_sales_category(7, 'webstore_sales')
#             write_sales_category(8, 'food_aggregators')

#             company_total = (
#                     pos_total +
#                     sum(total_per_category[k] for k in [
#                         'sale_order_mto', 'corporate_orders', 'custom_cakes',
#                         'wholesale_supply', 'webstore_sales', 'food_aggregators'
#                     ])
#             )
#             worksheet.merge_range(row, 9, end_row, 9, "{:.2f}".format(company_total), style_cell)

#             row = end_row + 2

#         worksheet.write(row, 1, 'Total Sales by Category', style_header)
#         worksheet.write(row, 2, "{:.2f}".format(total_per_category['walk_in_customers']), style_cell)
#         worksheet.write(row, 3, "{:.2f}".format(total_per_category['sale_order_mto']), style_cell)
#         worksheet.write(row, 4, "{:.2f}".format(total_per_category['corporate_orders']), style_cell)
#         worksheet.write(row, 5, "{:.2f}".format(total_per_category['custom_cakes']), style_cell)
#         worksheet.write(row, 6, "{:.2f}".format(total_per_category['wholesale_supply']), style_cell)
#         worksheet.write(row, 7, "{:.2f}".format(total_per_category['webstore_sales']), style_cell)
#         worksheet.write(row, 8, "{:.2f}".format(total_per_category['food_aggregators']), style_cell)

#         final_total = sum(total_per_category.values())
#         worksheet.write(row, 9, "{:.2f}".format(final_total), style_cell)

#         workbook.close()
#         xlsx_data = output.getvalue()

#         filename = "sales_report_%s_to_%s.xlsx" % (
#             self.from_date.strftime("%d-%m-%Y"),
#             self.to_date.strftime("%d-%m-%Y"),
#         )

#         self.write({
#             'xls_file': base64.encodebytes(xlsx_data),
#             'xls_filename': filename,
#         })

#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': self._name,
#             'view_mode': 'form',
#             'res_id': self.id,
#             'views': [(False, 'form')],
#             'target': 'new',
#         }

# def action_print_xlsx(self):
#     output = io.BytesIO()
#     workbook = xlsxwriter.Workbook(output, {'in_memory': True})
#     worksheet = workbook.add_worksheet('Sales Report')

#     style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
#     merge_formatb = workbook.add_format({
#         'bold': 1,
#         'border': 1,
#         'align': 'center',
#         'valign': 'vcenter',
#         'bg_color': '#FFFFFF',
#         'text_wrap': True
#     })
#     merge_formatb.set_font_size(9)

#     headers = [
#         "Outlet Name",
#         "PARTICULARS",
#         "Walk-in Customers (POS)",
#         "Sale Order (MTO)",
#         "Corporate Bulk Orders",
#         "Regular Institutional Orders",
#         "Custom Cakes",
#         "Wholesale Supply",
#         "Online Orders for pick up and home delivery",
#         "Total sales"
#     ]
#     row = 1
#     col = 0

#     for header in headers:
#         worksheet.write(row, col, header, style_highlight)
#         worksheet.set_column(col, col, 14)
#         col += 1
#     row += 1

#     total_per_category = {
#         'walk_in_customers': 0.0,
#         'sale_order_mto': 0.0,
#         'corporate_orders': 0.0,
#         'regular_orders': 0.0,
#         'custom_cakes': 0.0,
#         'wholesale_supply': 0.0,
#         'webstore_sales': 0.0,
#     }

#     selected_companies = self.company_ids
#     row = 4

#     for company in selected_companies:
#         sale_orders = self.env['sale.order'].search([
#             ('date_order', '>=', self.from_date),
#             ('date_order', '<=', self.to_date),
#             ('company_id', '=', company.id),
#             ('state', '=', 'sale'),
#         ])

#         end_row = row + 3
#         worksheet.merge_range(f'A{row}:A{end_row}', company.name or '', merge_formatb)

#         particulars = ['TOTAL SALES', 'BILL COUNT', 'ATV']
#         for index, particular in enumerate(particulars):
#             worksheet.write(f'B{row + index}', particular, merge_formatb)

#         # POS Walk-in Customers
#         pos_orders = self.env['pos.order'].search([
#             ('date_order', '>=', self.from_date),
#             ('date_order', '<=', self.to_date),
#             ('company_id', '=', company.id),
#         ])
#         sale_count = len(pos_orders)
#         pos_total = sum(pos_orders.mapped('amount_total'))
#         atv = pos_total / sale_count if sale_count else 0
#         worksheet.write(row, 2, sale_count, merge_formatb)
#         worksheet.write(row - 1, 2, "{:.2f}".format(pos_total), merge_formatb)
#         worksheet.write(row + 1, 2, "{:.2f}".format(atv), merge_formatb)
#         total_per_category['walk_in_customers'] += pos_total

#         def write_sales_category(col_index, sales_type_key):
#             filtered = [s for s in sale_orders if s.sales_types == sales_type_key]
#             count = len(filtered)
#             total = sum(s.amount_total for s in filtered)
#             atv = total / count if count else 0
#             worksheet.write(row, col_index, count, merge_formatb)
#             worksheet.write(row - 1, col_index, "{:.2f}".format(total), merge_formatb)
#             worksheet.write(row + 1, col_index, "{:.2f}".format(atv), merge_formatb)
#             total_per_category[sales_type_key] += total

#         write_sales_category(3, 'sale_order_mto')
#         write_sales_category(4, 'corporate_orders')
#         write_sales_category(5, 'regular_orders')
#         write_sales_category(6, 'custom_cakes')
#         write_sales_category(7, 'wholesale_supply')
#         write_sales_category(8, 'webstore_sales')

#         company_total = (
#             pos_total +
#             sum(
#                 sum(s.amount_total for s in sale_orders if s.sales_types == k)
#                 for k in ['sale_order_mto', 'corporate_orders', 'regular_orders', 'custom_cakes', 'wholesale_supply', 'webstore_sales']
#             )
#         )
#         worksheet.merge_range(f'J{row}:J{end_row}', "{:.2f}".format(company_total), merge_formatb)

#         row = end_row + 2

#     # Write Total Sales by Category
#     worksheet.write(row, 1, 'Total Sales by Category', style_highlight)
#     worksheet.write(row, 2, "{:.2f}".format(total_per_category['walk_in_customers']), merge_formatb)
#     worksheet.write(row, 3, "{:.2f}".format(total_per_category['sale_order_mto']), merge_formatb)
#     worksheet.write(row, 4, "{:.2f}".format(total_per_category['corporate_orders']), merge_formatb)
#     worksheet.write(row, 5, "{:.2f}".format(total_per_category['regular_orders']), merge_formatb)
#     worksheet.write(row, 6, "{:.2f}".format(total_per_category['custom_cakes']), merge_formatb)
#     worksheet.write(row, 7, "{:.2f}".format(total_per_category['wholesale_supply']), merge_formatb)
#     worksheet.write(row, 8, "{:.2f}".format(total_per_category['webstore_sales']), merge_formatb)

#     final_total = sum(total_per_category.values())
#     worksheet.write(row, 9, "{:.2f}".format(final_total), merge_formatb)

#     workbook.close()
#     xlsx_data = output.getvalue()
#     self.xls_file = base64.encodebytes(xlsx_data)
#     self.xls_filename = "sales_report.xlsx"

#     return {
#         'type': 'ir.actions.act_window',
#         'res_model': self._name,
#         'view_mode': 'form',
#         'res_id': self.id,
#         'views': [(False, 'form')],
#         'target': 'new',
#     }


# this works
# def action_print_xlsx(self):
#     output = io.BytesIO()
#     workbook = xlsxwriter.Workbook(output, {'in_memory': True})
#     worksheet = workbook.add_worksheet('Sales Report')

#     style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
#     merge_formatb = workbook.add_format({
#         'bold': 1,
#         'border': 1,
#         'align': 'center',
#         'valign': 'vcenter',
#         'bg_color': '#FFFFFF',
#         'text_wrap': True
#     })
#     merge_formatb.set_font_size(9)

#     headers = [
#         "Outlet Name",
#         "PARTICULARS",
#         "Walk-in Customers (POS)",
#         "Sale Order (MTO)",
#         "Corporate Bulk Orders",
#         "Regular Institutional Orders",
#         "Custom Cakes",
#         "Wholesale Supply",
#         "Online Orders for pick up and home delivery",
#         "Total sales"
#     ]
#     row = 1
#     col = 0

#     for header in headers:
#         worksheet.write(row, col, header, style_highlight)
#         worksheet.set_column(col, col, 14)
#         col += 1
#     row += 1

#     # Track total amounts per category across all companies
#     total_per_category = {
#         'walk_in_customers': 0.0,
#         'sale_order_mto': 0.0,
#         'corporate_orders': 0.0,
#         'custom_cakes': 0.0,
#         'wholesale_supply': 0.0,
#         'food_aggregators': 0.0,
#         'webstore_sales': 0.0,
#     }

#     selected_companies = self.company_ids
#     row = 4

#     for company in selected_companies:
#         sale_orders = self.env['sale.order'].search([
#             ('date_order', '>=', self.from_date),
#             ('date_order', '<=', self.to_date),
#             ('company_id', '=', company.id),
#             ('state', '=', 'sale'),
#         ])

#         if sale_orders:
#             end_row = row + 3
#             worksheet.merge_range(f'A{row}:A{end_row}', company.name or '', merge_formatb)

#             particulars = ['TOTAL SALES', 'BILL COUNT', 'ATV']
#             for index, particular in enumerate(particulars):
#                 worksheet.write(f'B{row + index}', particular, merge_formatb)

#             # Walk-in Customers (POS)
#             pos_orders = self.env['pos.order'].search([
#                 ('date_order', '>=', self.from_date),
#                 ('date_order', '<=', self.to_date),
#                 ('company_id', '=', company.id),
#             ])
#             sale_count = len(pos_orders)
#             pos_total = sum(pos_orders.mapped('amount_total'))
#             atv = pos_total / sale_count if sale_count else 0
#             worksheet.write(row, 2, sale_count, merge_formatb)
#             worksheet.write(row - 1, 2, "{:.2f}".format(pos_total), merge_formatb)
#             worksheet.write(row + 1, 2, "{:.2f}".format(atv), merge_formatb)
#             total_per_category['walk_in_customers'] += pos_total

#             def write_sales_category(col_index, sales_type_key):
#                 filtered = [s for s in sale_orders if s.sales_types == sales_type_key]
#                 count = len(filtered)
#                 total = sum(s.amount_total for s in filtered)
#                 atv = total / count if count else 0
#                 worksheet.write(row, col_index, count, merge_formatb)
#                 worksheet.write(row - 1, col_index, "{:.2f}".format(total), merge_formatb)
#                 worksheet.write(row + 1, col_index, "{:.2f}".format(atv), merge_formatb)
#                 total_per_category[sales_type_key] += total

#             write_sales_category(3, 'sale_order_mto')
#             write_sales_category(4, 'corporate_orders')
#             write_sales_category(5, 'custom_cakes')
#             write_sales_category(6, 'wholesale_supply')
#             write_sales_category(7, 'food_aggregators')
#             write_sales_category(8, 'webstore_sales')

#             overall_total = (
#                 pos_total +
#                 total_per_category['sale_order_mto'] +
#                 total_per_category['corporate_orders'] +
#                 total_per_category['custom_cakes'] +
#                 total_per_category['wholesale_supply'] +
#                 total_per_category['food_aggregators'] +
#                 total_per_category['webstore_sales']
#             )
#             worksheet.merge_range(f'J{row}:J{end_row}', "{:.2f}".format(overall_total), merge_formatb)

#             row = end_row + 2

#     # Write Total by Category at bottom
#     total_row_title = 'Total Sales by Category'
#     worksheet.write(row, 1, total_row_title, style_highlight)
#     worksheet.write(row, 2, "{:.2f}".format(total_per_category['walk_in_customers']), merge_formatb)
#     worksheet.write(row, 3, "{:.2f}".format(total_per_category['sale_order_mto']), merge_formatb)
#     worksheet.write(row, 4, "{:.2f}".format(total_per_category['corporate_orders']), merge_formatb)
#     worksheet.write(row, 5, "{:.2f}".format(total_per_category['custom_cakes']), merge_formatb)
#     worksheet.write(row, 6, "{:.2f}".format(total_per_category['wholesale_supply']), merge_formatb)
#     worksheet.write(row, 7, "{:.2f}".format(total_per_category['food_aggregators']), merge_formatb)
#     worksheet.write(row, 8, "{:.2f}".format(total_per_category['webstore_sales']), merge_formatb)

#     final_total = sum(total_per_category.values())
#     worksheet.write(row, 9, "{:.2f}".format(final_total), merge_formatb)

#     workbook.close()
#     xlsx_data = output.getvalue()
#     self.xls_file = base64.encodebytes(xlsx_data)
#     self.xls_filename = "sales_report.xlsx"

#     return {
#         'type': 'ir.actions.act_window',
#         'res_model': self._name,
#         'view_mode': 'form',
#         'res_id': self.id,
#         'views': [(False, 'form')],
#         'target': 'new',
#     }


# def action_print_xlsx(self):
#     output = io.BytesIO()
#     workbook = xlsxwriter.Workbook(output, {'in_memory': True})
#     worksheet = workbook.add_worksheet('Sales Report')
#     style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
#     merge_formatb = workbook.add_format({
#             'bold': 1,
#             'border': 1,
#             'align': 'center',
#             'valign': 'vcenter',
#             'bg_color': '#FFFFFF',
#             'text_wrap': True
#             })
#     merge_formatb.set_font_size(9)
#     headers = [
#         "Outlet Name",
#         "PARTICULARS",
#         "Walk-in Customers (POS)",
#         "Sale Order (MTO)",
#         "Corporate Bulk Orders",
#         "Regular Institutional Orders",
#         "Custom Cakes",
#         "Wholesale Supply",
#         "Online Orders for pick up and home delivery",
#         "Total sales"
#     ]
#     row = 1
#     col = 0

#     for header in headers:
#         worksheet.write(row, col, header, style_highlight)
#         worksheet.set_column(col, col, 14)
#         col += 1
#     row += 1

#     selected_companies = self.company_ids
#     sales_by_company = {}
#     row = 4

#     for company in selected_companies:
#         sale_orders = self.env['sale.order'].search([
#             ('date_order', '>=', self.from_date),
#             ('date_order', '<=', self.to_date),
#             ('company_id', '=', company.id),
#         ])
#         sales_by_company[company.name] = sale_orders

#         if sale_orders:
#             end_row = row + 3
#             worksheet.merge_range(f'A{row}:A{end_row}', company.name or '', merge_formatb)

#             particulars = ['TOTAL SALES', 'BILL COUNT', 'ATV']
#             for index, particular in enumerate(particulars):
#                 worksheet.write(f'B{row + index}', particular, merge_formatb)

#             walk_in_customers = self.env['pos.order'].search([
#                 ('date_order', '>=', self.from_date),
#                 ('date_order', '<=', self.to_date),
#                 ('company_id', '=', company.id),
#             ])

#             sale_count = len(walk_in_customers)
#             print("...................................",sale_count)
#             pos_total_amount = sum(walk_in_customers.mapped('amount_total'))
#             divide_col = pos_total_amount / sale_count if sale_count else 0

#             worksheet.write(row, 2, sale_count, merge_formatb)
#             worksheet.write(row - 1, 2, "{:.2f}".format(pos_total_amount), merge_formatb)
#             worksheet.write(row + 1, 2, "{:.2f}".format(divide_col), merge_formatb)


#             sale_orders = self.env['sale.order'].search([
#                 ('date_order', '>=', self.from_date),
#                 ('date_order', '<=', self.to_date),
#                 ('company_id', '=', company.id),
#                 ('state','=','sale')
#             ])


#             filtered_sales = [sale for sale in sale_orders if sale.sales_types == 'sale_order_mto']
#             sale_count_1 = len(filtered_sales)
#             pos_total_amount_1 = sum(sale.amount_total for sale in filtered_sales)
#             divide_col_1 = pos_total_amount_1 / sale_count_1 if sale_count_1 else 0

#             worksheet.write(row, 3, sale_count_1, merge_formatb)
#             worksheet.write(row - 1, 3, "{:.2f}".format(pos_total_amount_1), merge_formatb)
#             worksheet.write(row + 1, 3, "{:.2f}".format(divide_col_1), merge_formatb)

#             filtered_sales_1 = [sale for sale in sale_orders if sale.sales_types == 'corporate_orders']
#             sale_count_2 = len(filtered_sales_1)
#             pos_total_amount_2 = sum(sale.amount_total for sale in filtered_sales_1)
#             divide_col_2 = pos_total_amount_2 / sale_count_2 if sale_count_2 else 0

#             worksheet.write(row, 4, sale_count_2, merge_formatb)
#             worksheet.write(row - 1, 4, "{:.2f}".format(pos_total_amount_2), merge_formatb)
#             worksheet.write(row + 1, 4, "{:.2f}".format(divide_col_2), merge_formatb)

#             filtered_sales_2 = [sale for sale in sale_orders if sale.sales_types == 'custom_cakes']
#             sale_count_3 = len(filtered_sales_2)
#             pos_total_amount_3 = sum(sale.amount_total for sale in filtered_sales_2)
#             divide_col_3 = pos_total_amount_3 / sale_count_3 if sale_count_3 else 0

#             worksheet.write(row, 5, sale_count_3, merge_formatb)
#             worksheet.write(row - 1, 5, "{:.2f}".format(pos_total_amount_3), merge_formatb)
#             worksheet.write(row + 1, 5, "{:.2f}".format(divide_col_3), merge_formatb)

#             filtered_sales_3 = [sale for sale in sale_orders if sale.sales_types == 'wholesale_supply']
#             sale_count_4 = len(filtered_sales_3)
#             pos_total_amount_4 = sum(sale.amount_total for sale in filtered_sales_3)
#             divide_col_4 = pos_total_amount_4 / sale_count_4 if sale_count_4 else 0

#             worksheet.write(row, 6, sale_count_4, merge_formatb)
#             worksheet.write(row - 1, 6, "{:.2f}".format(pos_total_amount_4), merge_formatb)
#             worksheet.write(row + 1, 6, "{:.2f}".format(divide_col_4), merge_formatb)

#             filtered_sales_4 = [sale for sale in sale_orders if sale.sales_types == 'food_aggregators']

#             sale_count_5 = len(filtered_sales_4)
#             pos_total_amount_5 = sum(sale.amount_total for sale in filtered_sales_4)
#             divide_col_5 = pos_total_amount_5 / sale_count_5 if sale_count_5 else 0

#             worksheet.write(row, 7, sale_count_5, merge_formatb)
#             worksheet.write(row - 1, 7, "{:.2f}".format(pos_total_amount_5), merge_formatb)
#             worksheet.write(row + 1, 7, "{:.2f}".format(divide_col_5), merge_formatb)

#             filtered_sales_5 = [sale for sale in sale_orders if sale.sales_types == 'webstore_sales']
#             sale_count_6 = len(filtered_sales_5)
#             pos_total_amount_6 = sum(sale.amount_total for sale in filtered_sales_5)
#             divide_col_6 = pos_total_amount_6 / sale_count_6 if sale_count_6 else 0

#             worksheet.write(row, 8, sale_count_6, merge_formatb)
#             worksheet.write(row - 1, 8, "{:.2f}".format(pos_total_amount_6), merge_formatb)
#             worksheet.write(row + 1, 8, "{:.2f}".format(divide_col_6), merge_formatb)

#             over_all_total_sales = pos_total_amount  + pos_total_amount_2 + pos_total_amount_3 + pos_total_amount_4 + pos_total_amount_5 + pos_total_amount_6
#             worksheet.merge_range(f'J{row}:J{end_row}', over_all_total_sales or '', merge_formatb)

#             row = end_row + 1
#         row += 1


#     workbook.close()
#     xlsx_data = output.getvalue()
#     self.xls_file = base64.encodebytes(xlsx_data)
#     self.xls_filename = "sales_report.xlsx"

#     return {
#         'type': 'ir.actions.act_window',
#         'res_model': self._name,
#         'view_mode': 'form',
#         'res_id': self.id,
#         'views': [(False, 'form')],
#         'target': 'new',
#         }
