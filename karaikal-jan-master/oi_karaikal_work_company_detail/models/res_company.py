from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    name_of_company = fields.Char(string="Name of the Company", required=True)