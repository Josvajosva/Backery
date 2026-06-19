from odoo import models, fields, api, _
from datetime import date, timedelta, datetime, timezone
from odoo.fields import Date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
import io
import xlsxwriter
import base64
import json


class SaleCashReportWizard(models.TransientModel):
    _name = 'sale.cash.report.wizard'
    _description = 'Sale Cash Report Wizard'

    from_date = fields.Date('Date', default=fields.date.today())
    to_date = fields.Date("To Date")
    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    company_ids = fields.Many2many('res.company', 'companies_sale_cash_report_wizard_relation',
                                   'sale_cash_report_wizard_id', 'company_id', string="Companies",
                                   default=lambda self: self.env.company)
    report_data = fields.Text("Report Data", readonly=True)

    @api.model
    def default_get(self, fields):
        context = self._context
        res = super().default_get(fields)
        res.update({
            'company_ids': [(6, 0, context['allowed_company_ids'])],
            'company_id': context['allowed_company_ids'][0],
        })
        return res

    def generate_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Sales Report')

        header_format = workbook.add_format({'bold': True, 'bg_color': '#E0E0E0', 'align': 'center', 'border': 1})
        cell_format = workbook.add_format({'align': 'center', 'border': 1})
        currency_format = workbook.add_format({'num_format': '#,##0.00', 'align': 'center', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'border': 1})
        row = 0
        col = 0
        worksheet.merge_range(row, 0, row, 2, 'Sales Report', title_format)
        row += 1
        worksheet.write(row, 0, 'Date', header_format)
        worksheet.write(row, 1, self.from_date.strftime('%d/%m/%Y'), header_format)
        row += 1

        worksheet.write(row, 0, '', header_format)
        company_names = [company.name for company in self.company_ids]
        for idx, company_name in enumerate(company_names):
            worksheet.write(row, idx + 1, company_name, header_format)
        total_col_index = len(company_names) + 1
        worksheet.write(row, total_col_index, 'Total', header_format)
        row += 1
        worksheet.write(row, 0, 'Sales From POS', header_format)
        pos_totals = []
        for company in self.company_ids:
            matching_order = []
            pos_orders = self.env['pos.order'].search([
                ('company_id', '=', company.id),
                ('state', 'in', ['paid', 'done']),
            ])
            for rec in pos_orders:
                date = rec.date_order.date()
                if date == self.from_date:
                    matching_order.append(rec)

            pos_total = sum(order.amount_total for order in matching_order)
            pos_totals.append(pos_total)
            worksheet.write(row, company_names.index(company.name) + 1, pos_total or 0, currency_format)
        overall_total = sum(pos_totals)
        worksheet.write(row, total_col_index, overall_total or 0, currency_format)
        row += 1

        worksheet.write(row, 0, 'Sales from Sales App', header_format)
        sale_app_totals = []
        for company in self.company_ids:
            matching_order = []
            account_move = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
            ])
            for move in account_move:
                date = move.invoice_date
                if date == self.from_date:
                    matching_order.append(move)
            total = sum(line.amount_total for line in matching_order)
            sale_app_totals.append(total)
            worksheet.write(row, company_names.index(company.name) + 1, total, currency_format)
        sale_overall_total = sum(sale_app_totals)
        worksheet.write(row, total_col_index, sale_overall_total or 0, currency_format)
        row += 1
        total_sales_per_company = [pos + sale for pos, sale in zip(pos_totals, sale_app_totals)]
        worksheet.write(row, 0, 'Total Sales', header_format)
        for idx, total in enumerate([pos + sale for pos, sale in zip(pos_totals, sale_app_totals)]):
            worksheet.write(row, idx + 1, total, currency_format)

        overall_total_sales = sum(total_sales_per_company)
        worksheet.write(row, len(company_names) + 1, overall_total_sales or 0, currency_format)
        row += 4

        # Cash / Bank Book
        worksheet.merge_range(row, 0, row, 2, 'Cash / Bank Book', title_format)
        row += 1
        worksheet.write(row, 0, 'Date', header_format)
        worksheet.write(row, 1, self.from_date.strftime('%d/%m/%Y'), header_format)
        row += 1

        worksheet.write(row, 0, '', header_format)
        col = 1
        for company in self.company_ids:
            worksheet.merge_range(row, col, row, col + 1, company.name, header_format)
            col += 2
        worksheet.write(row, col, 'Total', header_format)
        row += 1

        worksheet.write(row, 0, 'Particulars', header_format)
        col = 1
        for _ in self.company_ids:
            worksheet.write(row, col, 'Cash', header_format)
            worksheet.write(row, col + 1, 'Bank', header_format)
            col += 2
        worksheet.write(row, col, '', header_format)
        row += 1

        # Initialize totals for final Closing Balance
        opening_cash = []
        opening_bank = []
        pos_cash_totals = []
        pos_bank_totals = []
        settlement_cash = []
        settlement_bank = []
        sales_cash = []
        sales_bank = []

        # Opening Balance
        worksheet.write(row, 0, 'Opening Balance', header_format)
        col = 1
        for company in self.company_ids:
            matching_order = self.env['pos.session'].search([
                ('company_id', '=', company.id),
                ('state', 'in', ['closed', 'opened']),
                ('start_at', '>=', self.from_date),
                ('start_at', '<', self.from_date + timedelta(days=1)),
            ])
            cash_start = sum(order.cash_register_balance_start for order in matching_order)
            opening_cash.append(cash_start)
            opening_bank.append(0)

            worksheet.write(row, col, cash_start or 0, currency_format)
            worksheet.write(row, col + 1, 0, currency_format)
            col += 2
        worksheet.write(row, col, sum(opening_cash), currency_format)
        row += 1

        # POS Cash
        worksheet.write(row, 0, 'POS Cash', header_format)
        col = 1
        for company in self.company_ids:
            cash_payment = 0
            bank_payment = 0
            pos_payments = self.env['pos.payment'].search([('company_id', '=', company.id)])
            for rec in pos_payments:
                if rec.payment_date.date() == self.from_date:
                    journal_type = rec.payment_method_id.journal_id.type
                    if journal_type == 'cash':
                        cash_payment += rec.amount
                    elif journal_type == 'bank':
                        bank_payment += rec.amount

            pos_cash_totals.append(cash_payment)
            pos_bank_totals.append(bank_payment)

            worksheet.write(row, col, cash_payment or 0, currency_format)
            worksheet.write(row, col + 1, bank_payment or 0, currency_format)
            col += 2
        worksheet.write(row, col, sum(pos_cash_totals) + sum(pos_bank_totals), currency_format)
        row += 1

        # Settlement
        worksheet.write(row, 0, 'Settlement', header_format)
        col = 1
        for company in self.company_ids:
            cash_payment = 0
            bank_payment = 0
            acc_payments = self.env['account.payment'].search([
                ('company_id', '=', company.id),
                ('payment_type', '=', 'inbound'),
                ('settlement', '=', 'settlement'),
                ('state', 'in', ['in_process', 'paid']),

            ])
            for rec in acc_payments:
                if rec.date == self.from_date:
                    journal_type = rec.journal_id.type
                    if journal_type == 'cash':
                        cash_payment += rec.amount
                    elif journal_type == 'bank':
                        bank_payment += rec.amount

            settlement_cash.append(cash_payment)
            settlement_bank.append(bank_payment)

            worksheet.write(row, col, cash_payment or 0, currency_format)
            worksheet.write(row, col + 1, bank_payment or 0, currency_format)
            col += 2
        worksheet.write(row, col, sum(settlement_cash) + sum(settlement_bank), currency_format)
        row += 1

        # Sale
        worksheet.write(row, 0, 'Sale', header_format)
        col = 1
        for company in self.company_ids:
            cash_payment = 0
            bank_payment = 0
            sales = self.env['account.payment'].search([
                ('company_id', '=', company.id),
                ('payment_type', '=', 'inbound'),
                ('settlement', '=', ''),
                ('state', 'in', ['in_process', 'paid']),
            ])
            for rec in sales:
                if rec.date == self.from_date:
                    journal_type = rec.journal_id.type
                    if journal_type == 'cash':
                        cash_payment += rec.amount
                    elif journal_type == 'bank':
                        bank_payment += rec.amount

            sales_cash.append(cash_payment)
            sales_bank.append(bank_payment)

            worksheet.write(row, col, cash_payment or 0, currency_format)
            worksheet.write(row, col + 1, bank_payment or 0, currency_format)
            col += 2
        worksheet.write(row, col, sum(sales_cash) + sum(sales_bank), currency_format)
        row += 1
        # Closing Balance
        worksheet.write(row, 0, 'Closing Balance', header_format)
        col = 1
        closing_cash = []
        closing_bank = []

        for i in range(len(self.company_ids)):
            total_cash = (
                    opening_cash[i] +
                    pos_cash_totals[i] +
                    settlement_cash[i] +
                    sales_cash[i]
            )
            total_bank = (
                    opening_bank[i] +
                    pos_bank_totals[i] +
                    settlement_bank[i] +
                    sales_bank[i]
            )

            worksheet.write(row, col, total_cash or 0, currency_format)
            worksheet.write(row, col + 1, total_bank or 0, currency_format)
            col += 2

            closing_cash.append(total_cash)
            closing_bank.append(total_bank)

        # Total (cash + bank)
        worksheet.write(row, col, sum(closing_cash) + sum(closing_bank), currency_format)

        row += 1
        worksheet.write(row, 0, 'Deposit to Bank', header_format)
        col = 1
        for i in range(len(self.company_ids)):
            deposit_cash = closing_cash[i] - opening_cash[i]
            deposit_bank = closing_bank[i] - opening_bank[i]

            worksheet.write(row, col, deposit_cash or 0, currency_format)
            worksheet.write(row, col + 1, deposit_bank or 0, currency_format)
            col += 2
        total_cash_diff = sum(closing_cash) - sum(opening_cash)
        total_bank_diff = sum(closing_bank) - sum(opening_bank)
        worksheet.write(row, col, total_cash_diff + total_bank_diff, currency_format)

        report_dict = {
            'from_date': self.from_date.strftime('%d/%m/%Y'),
            'companies': [c.name for c in self.company_ids],
            'pos_totals': pos_totals,
            'sale_app_totals': sale_app_totals,
            'total_sales': total_sales_per_company,
            'overall_total_sales': overall_total_sales,
            'opening_cash': opening_cash,
            'opening_bank': opening_bank,
            'pos_cash': pos_cash_totals,
            'pos_bank': pos_bank_totals,
            'settlement_cash': settlement_cash,
            'settlement_bank': settlement_bank,
            'sales_cash': sales_cash,
            'sales_bank': sales_bank,
            'closing_cash': closing_cash,
            'closing_bank': closing_bank,
            'deposit_cash': [closing - opening for closing, opening in zip(closing_cash, opening_cash)],
            'deposit_bank': [closing - opening for closing, opening in zip(closing_bank, opening_bank)],
        }

        self.report_data = json.dumps(report_dict)

        workbook.close()
        output.seek(0)

        return ('sales_cash_report.xlsx', output.read())
        # xlsx_data = output.getvalue()
        # self.xls_file = base64.encodebytes(xlsx_data)
        # self.xls_filename = "daily_sales_cash_report.xlsx"

        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': self._name,
        #     'view_mode': 'form',
        #     'res_id': self.id,
        #     'views': [(False, 'form')],
        #     'target': 'new',
        # }

    def actions_fixed_reports(self):
        self.generate_report_html_data()
        return self.env.ref('oi_karaikal_sale_cash_report.fixed_report_view').report_action(self)

    def generate_report_html_data(self):
        data = {
            'from_date': self.from_date.strftime('%d/%m/%Y'),
            'companies': [company.name for company in self.company_ids],
            'sales': {
                'pos': [],
                'sales_app': [],
                'total': []
            },
            'cash_book': {
                'opening_balance': [],
                'pos_cash': [],
                'settlement': [],
                'sales': [],
                'closing_balance': [],
                'deposit_to_bank': []
            }
        }

        for company in self.company_ids:
            pos_orders = self.env['pos.order'].search([
                ('company_id', '=', company.id),
                ('state', 'in', ['paid', 'done']),
            ])
            pos_total = sum(order.amount_total for order in pos_orders if order.date_order.date() == self.from_date)
            data['sales']['pos'].append(pos_total)
            account_move = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
            ])
            sales_app_total = sum(move.amount_total for move in account_move if move.invoice_date == self.from_date)
            data['sales']['sales_app'].append(sales_app_total)
            data['sales']['total'].append(pos_total + sales_app_total)
            session = self.env['pos.session'].search([
                ('company_id', '=', company.id),
                ('start_at', '>=', self.from_date),
                ('start_at', '<', self.from_date + timedelta(days=1)),
            ])
            opening_cash = sum(s.cash_register_balance_start for s in session)
            data['cash_book']['opening_balance'].append({'cash': opening_cash, 'bank': 0})
            cash = bank = 0
            for p in self.env['pos.payment'].search([('company_id', '=', company.id)]):
                if p.payment_date.date() == self.from_date:
                    jtype = p.payment_method_id.journal_id.type
                    if jtype == 'cash':
                        cash += p.amount
                    elif jtype == 'bank':
                        bank += p.amount
            data['cash_book']['pos_cash'].append({'cash': cash, 'bank': bank})
            cash = bank = 0
            for p in self.env['account.payment'].search([
                ('company_id', '=', company.id),
                ('payment_type', '=', 'inbound'),
                ('settlement', '=', 'settlement'),
                ('state', 'in', ['in_process', 'paid']),
            ]):
                if p.date == self.from_date:
                    jtype = p.journal_id.type
                    if jtype == 'cash':
                        cash += p.amount
                    elif jtype == 'bank':
                        bank += p.amount
            data['cash_book']['settlement'].append({'cash': cash, 'bank': bank})
            cash = bank = 0
            for p in self.env['account.payment'].search(
                    [('company_id', '=', company.id), ('state', 'in', ['in_process', 'paid']),
                     ('payment_type', '=', 'inbound'), ('settlement', '=', ''), ]):
                if p.date == self.from_date:
                    jtype = p.journal_id.type
                    if jtype == 'cash':
                        cash += p.amount
                    elif jtype == 'bank':
                        bank += p.amount
            data['cash_book']['sales'].append({'cash': cash, 'bank': bank})
            cc = data['cash_book']['opening_balance'][-1]['cash'] + data['cash_book']['pos_cash'][-1]['cash'] + \
                 data['cash_book']['settlement'][-1]['cash'] + data['cash_book']['sales'][-1]['cash']
            cb = data['cash_book']['opening_balance'][-1]['bank'] + data['cash_book']['pos_cash'][-1]['bank'] + \
                 data['cash_book']['settlement'][-1]['bank'] + data['cash_book']['sales'][-1]['bank']
            data['cash_book']['closing_balance'].append({'cash': cc, 'bank': cb})
            data['cash_book']['deposit_to_bank'].append({'cash': cc - data['cash_book']['opening_balance'][-1]['cash'],
                                                         'bank': cb - data['cash_book']['opening_balance'][-1]['bank']})
        self.report_data = json.dumps(data)