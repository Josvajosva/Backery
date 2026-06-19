from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    daily_reports_mail_id = fields.Char(string="Daily Reports Email ID", help="Email ID of the Director to receive the daily consolidated Unmoved and Variance Stock Reports")
