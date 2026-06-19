import io
import datetime
import pytz
from odoo import http, _
from odoo.http import request
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

class LoyaltyReportController(http.Controller):
    
    @http.route('/loyalty_report/download', type='http', auth='user')
    def download_loyalty_report(self, wizard_id, **kw):
        wizard = request.env['loyalty.report.wizard'].browse(int(wizard_id))
        if not wizard.exists():
            return request.not_found()

        if not xlsxwriter:
            return request.make_response("xlsxwriter is not installed.", headers=[('Content-Type', 'text/plain')])

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Loyalty History')
        
        # --- Formats ---
        title_style = workbook.add_format({
            'bold': True, 'font_size': 18, 'align': 'center', 'valign': 'vcenter', 'font_color': '#1f4e78'
        })
        subtitle_style = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter', 'font_color': '#3b3838'
        })
        header_style = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#1f4e78', 'font_color': '#ffffff', 'border': 1
        })
        cell_style = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        zebra_cell_style = workbook.add_format({'border': 1, 'valign': 'vcenter', 'bg_color': '#f2f2f2'})
        
        date_style = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'valign': 'vcenter', 'align': 'center'})
        zebra_date_style = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'valign': 'vcenter', 'bg_color': '#f2f2f2', 'align': 'center'})
        
        num_style = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'valign': 'vcenter'})
        zebra_num_style = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'valign': 'vcenter', 'bg_color': '#f2f2f2'})
        
        total_label_style = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#d9d9d9', 'align': 'right'})
        total_num_style = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#d9d9d9', 'num_format': '#,##0.00'})
        
        # --- Layout ---
        worksheet.set_column('A:A', 35) # Customer
        worksheet.set_column('B:B', 15) # Date
        worksheet.set_column('C:D', 15) # Earned, Redeemed

        # --- Report Header ---
        worksheet.merge_range('A1:D1', 'LOYALTY HISTORY REPORT', title_style)
        worksheet.set_row(0, 30)
        
        worksheet.write('A2', 'Period:', subtitle_style)
        worksheet.write('B2', f"{wizard.start_date} to {wizard.end_date}")
        worksheet.write('A3', 'Printed On:', subtitle_style)
        worksheet.write('B3', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        row = 5
        headers = ['Customer', 'Date', 'Earned', 'Redeemed']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_style)
        row += 1

        # --- Data Logic ---
        user_tz = request.env.user.tz or 'UTC'
        local = pytz.timezone(user_tz)
        start_dt_utc = local.localize(datetime.datetime.combine(wizard.start_date, datetime.time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end_dt_utc = local.localize(datetime.datetime.combine(wizard.end_date, datetime.time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        domain = [('create_date', '>=', start_dt_utc), ('create_date', '<=', end_dt_utc)]
        if wizard.partner_ids:
            domain.append(('card_id.partner_id', 'in', wizard.partner_ids.ids))
            
        points_cond = []
        if wizard.check_earned: points_cond.append(('issued', '>', 0))
        if wizard.check_redeemed: points_cond.append(('used', '>', 0))
        if len(points_cond) == 2:
            domain.append('|')
            domain.extend(points_cond)
        elif len(points_cond) == 1:
            domain.append(points_cond[0])
            
        histories = request.env['loyalty.history'].search(domain, order='create_date asc')
        
        total_earned = 0
        total_used = 0

        for i, history in enumerate(histories):
            is_zebra = i % 2 == 1
            c_style = zebra_cell_style if is_zebra else cell_style
            d_style = zebra_date_style if is_zebra else date_style
            n_style = zebra_num_style if is_zebra else num_style
            
            partner_name = history.card_id.partner_id.name or 'Unknown Partner'
            worksheet.write(row, 0, partner_name, c_style)
            
            # Date (Date only)
            create_date_local = pytz.UTC.localize(history.create_date).astimezone(local).replace(tzinfo=None) if history.create_date else None
            if create_date_local:
                worksheet.write_datetime(row, 1, create_date_local.date(), d_style)
            else:
                worksheet.write(row, 1, '', c_style)
                
            worksheet.write(row, 2, history.issued, n_style)
            worksheet.write(row, 3, history.used, n_style)
            
            total_earned += history.issued
            total_used += history.used
            row += 1
            
        # --- Grand Total ---
        row += 1
        worksheet.merge_range(row, 0, row, 1, 'GRAND TOTAL', total_label_style)
        worksheet.write(row, 2, total_earned, total_num_style)
        worksheet.write(row, 3, total_used, total_num_style)

        workbook.close()
        output.seek(0)
        
        file_name = f"Loyalty_History_{wizard.start_date}_to_{wizard.end_date}.xlsx"
        
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{file_name}"')
            ]
        )
