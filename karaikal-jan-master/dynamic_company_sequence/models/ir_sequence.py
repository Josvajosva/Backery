from datetime import datetime
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    sequence_config_id = fields.Many2one('sequence.config', string="Sequence Config")

    def _get_prefix_suffix(self, date=None, date_range=None):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            now = range_date = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            if date or self._context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(date or self._context.get('ir_sequence_date'))
            if date_range or self._context.get('ir_sequence_date_range'):
                range_date = fields.Datetime.from_string(date_range or self._context.get('ir_sequence_date_range'))

            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, fmt in sequences.items():
                res[key] = effective_date.strftime(fmt)
                res['range_' + key] = range_date.strftime(fmt)
                res['current_' + key] = now.strftime(fmt)

            # Custom financial year logic for %(range_year)s
            # Financial year: April to March
            if effective_date.month >= 4:
                start_year = effective_date.year
                end_year = effective_date.year + 1
            else:
                start_year = effective_date.year - 1
                end_year = effective_date.year

            fy_str = f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"
            res['range_year'] = fy_str
            
            return res

        self.ensure_one()
        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
            interpolated_suffix = _interpolate(self.suffix, d)
        except (ValueError, TypeError):
            raise UserError(_('Invalid prefix or suffix for sequence "%s"', self.name))
        return interpolated_prefix, interpolated_suffix
