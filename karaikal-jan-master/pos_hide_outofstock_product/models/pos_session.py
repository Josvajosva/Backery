from odoo import models

class PosSession(models.Model):
    _inherit = "pos.session"

    # Tell POS to load product.category model
    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if "product.category" not in result:
            result.append("product.category")
        return result
