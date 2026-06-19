from odoo import models, fields


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    is_inter_company = fields.Boolean(string="Inter-Company?", default=False)