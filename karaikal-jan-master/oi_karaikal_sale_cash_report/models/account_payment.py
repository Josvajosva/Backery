from odoo import models,fields,api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    settlement = fields.Selection(
        [('settlement', 'Settlement')],
        string='Settlement')