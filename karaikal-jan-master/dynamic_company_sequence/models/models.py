from odoo import models, fields, api, _
from datetime import datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    expected_currency_rate = fields.Float(
        string="Expected Currency Rate"
    )

    def action_post(self):
        res = super().action_post()

        for move in self:

            # ✅ Only for invoices & bills
            if move.move_type not in ['out_invoice', 'in_invoice']:
                continue
            move.name = '/'

            # ✅ Company
            company = move.company_id
            code = company.code or 'NEW'

            # ✅ Invoice Date
            invoice_date = move.invoice_date or fields.Date.today()
            year = invoice_date.year

            # ✅ Financial Year (April–March)
            if invoice_date.month >= 4:
                fy_start = year
                fy_end = year + 1
            else:
                fy_start = year - 1
                fy_end = year

            fy = f"{str(fy_start)[-2:]}-{str(fy_end)[-2:]}"

            # ✅ Decide Type
            if move.move_type == 'out_invoice':
                inv_type = 'CINV'   # Customer Invoice
            elif move.move_type == 'in_invoice':
                inv_type = 'PINV'   # Purchase Invoice

            # ✅ Sequence
            seq_full = self.env['ir.sequence'] \
                           .with_company(company.id) \
                           .next_by_code('account.move') or '00001'

            seq_number = seq_full.split('/')[-1]

            # ✅ Final Name
            move.name = f"{code}/{fy}/{inv_type}/{seq_number}"

        return res

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    analytic_distribution = fields.Json(string="Analytic Distribution")

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def create(self, vals):

        if vals.get('name', 'New') == 'New':

            # ✅ Company
            company_id = vals.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)

            code = company.code or 'NEW'

            # ✅ Order date
            order_date = vals.get('date_order')
            if order_date:
                order_date = fields.Datetime.from_string(order_date)
            else:
                order_date = fields.Datetime.now()

            year = order_date.year

            # ✅ Financial Year
            if order_date.month >= 4:
                fy_start = year
                fy_end = year + 1
            else:
                fy_start = year - 1
                fy_end = year

            fy = f"{str(fy_start)[-2:]}-{str(fy_end)[-2:]}"

            seq_full = self.env['ir.sequence']\
                .with_company(company_id)\
                .next_by_code('purchase.order') or '00001'

            seq_number = seq_full.split('/')[-1]

            vals['name'] = f"{code}/{fy}/PO/{seq_number}"

        return super().create(vals)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in ['New', '/']:

            # ✅ Company
            company_id = vals.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            code = company.code or 'NEW'

            # ✅ Order Date
            order_date = vals.get('date_order')
            if order_date:
                order_date = fields.Datetime.to_datetime(order_date)
            else:
                order_date = fields.Datetime.now()

            year = order_date.year

            # ✅ Dynamic Financial Year (April → March)
            if order_date.month >= 4:
                fy_start = year
                fy_end = year + 1
            else:
                fy_start = year - 1
                fy_end = year

            fy = f"{str(fy_start)[-2:]}-{str(fy_end)[-2:]}"

            # ✅ Get sequence
            seq_full = self.env['ir.sequence'] \
                .with_company(company_id) \
                .next_by_code('sale.order') or '00001'

            seq_number = seq_full.split('/')[-1]

            # ✅ Final Sale Order Name
            vals['name'] = f"{code}/{fy}/SO/{seq_number}"

        return super().create(vals)