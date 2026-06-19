from odoo import models, fields

class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    is_inter_company = fields.Boolean(string="Inter-Company?", default=False)

# End of partner category inheritance