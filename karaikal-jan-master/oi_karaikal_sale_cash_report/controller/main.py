from odoo import http
from odoo.http import request
import base64


class ReportDownloadController(http.Controller):

    @http.route('/web/binary/download_excel_report', type='http', auth='user')
    def download_excel_report(self, wizard_id):
        wizard = request.env['sale.cash.report.wizard'].sudo().browse(int(wizard_id))
        wizard.generate_report_html_data()
        filename, content = wizard.generate_report()

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}'),
            ]
        )