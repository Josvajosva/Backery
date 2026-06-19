from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    validate_grn_from_invoice = fields.Boolean(
        string='Validate GRN from Invoice',
    )
    