from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_hide_outofstock_products = fields.Boolean(
        related="pos_config_id.hide_outofstock_products",
        readonly=False
    )

