from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = "res.company"
    
    hide_franchise_span = fields.Boolean(
        string='Hide Franchise Span',
        default=False
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Override to load custom fields into POS"""
        fields_to_load = super()._load_pos_data_fields(config_id)
        fields_to_load += ['hide_franchise_span']
        return fields_to_load
