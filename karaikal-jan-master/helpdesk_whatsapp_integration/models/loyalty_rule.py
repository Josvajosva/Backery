from odoo import api, fields, models


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    floor_calculation = fields.Boolean(
        string='Floor Calculation',
        default=False,
        help='When enabled, points are calculated based on complete multiples of the '
             'minimum purchase amount only. For example, if the rule is "5 points per 100 RS", '
             'then 165 RS = 5 points, 200 RS = 10 points, 350 RS = 15 points.',
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ['floor_calculation', 'sequence']
        return fields