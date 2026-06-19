from odoo import models, fields, api

class SequenceConfig(models.Model):
    _name = 'sequence.config'
    _description = 'Sequence Configuration'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Sequence Code', required=True)
    short_code = fields.Char(string='Short Code Prefix', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        configs = super().create(vals_list)
        companies = self.env['res.company'].search([('code', '!=', False)])
        configs._generate_sequences(companies)
        return configs

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ['code', 'short_code', 'name']):
            companies = self.env['res.company'].search([('code', '!=', False)])
            self._generate_sequences(companies)
        return res

    def _generate_sequences(self, companies):
        IrSequence = self.env['ir.sequence'].sudo()

        for config in self:
            for company in companies:
                if not company.code:
                    continue

                prefix = f"{company.code}/%(range_year)s/{config.short_code}/"

                # 🔴 FIRST: Try finding by config link (BEST MATCH)
                sequence = IrSequence.search([
                    ('sequence_config_id', '=', config.id),
                    ('company_id', '=', company.id)
                ], limit=1)

                # 🔴 SECOND: fallback → detect manual sequences
                if not sequence:
                    sequence = IrSequence.search([
                        ('code', '=', config.code),
                        ('company_id', '=', company.id)
                    ], limit=1)

                seq_vals = {
                    'name': f"{config.name} ({company.name})",
                    'code': config.code,
                    'company_id': company.id,
                    'prefix': prefix,
                    'padding': 5,
                    'use_date_range': True,
                    'sequence_config_id': config.id,
                }

                if sequence:
                    sequence.write(seq_vals)  # ✅ OVERRIDE manual also
                else:
                    IrSequence.create(seq_vals)
