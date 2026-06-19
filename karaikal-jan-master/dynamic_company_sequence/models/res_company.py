from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    code = fields.Char(string='Company Short Code', help='Used as prefix in sequences (e.g., KZ, FC)')

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._create_or_update_sequences()
        return companies

    def write(self, vals):
        res = super().write(vals)
        if 'code' in vals:
            self._create_or_update_sequences()
        return res

    def _create_or_update_sequences(self):
        configs = self.env['sequence.config'].search([])
        if configs:
            configs._generate_sequences(self)
