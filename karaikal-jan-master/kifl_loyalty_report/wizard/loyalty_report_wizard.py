import datetime
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoyaltyReportWizard(models.TransientModel):
    _name = 'loyalty.report.wizard'
    _description = 'Loyalty Report Wizard'

    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    end_date = fields.Date(string='End Date', required=True, default=fields.Date.context_today)
    partner_ids = fields.Many2many('res.partner', string='Customers')
    check_earned = fields.Boolean(string='Earned', default=True)
    check_redeemed = fields.Boolean(string='Redeemed', default=True)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_('Start Date cannot be greater than End Date.'))

    def action_generate_excel(self):
        self.ensure_one()
        if not self.check_earned and not self.check_redeemed:
            raise ValidationError(_('Please select at least one transaction type (Earned or Redeemed).'))
        
        # Validation for records existence
        user_tz = self.env.user.tz or 'UTC'
        local = pytz.timezone(user_tz)

        start_dt_local = local.localize(datetime.datetime.combine(self.start_date, datetime.time.min))
        end_dt_local = local.localize(datetime.datetime.combine(self.end_date, datetime.time.max))

        start_dt_utc = start_dt_local.astimezone(pytz.UTC).replace(tzinfo=None)
        end_dt_utc = end_dt_local.astimezone(pytz.UTC).replace(tzinfo=None)

        domain = [
            ('create_date', '>=', start_dt_utc),
            ('create_date', '<=', end_dt_utc)
        ]
        
        if self.partner_ids:
            domain.append(('card_id.partner_id', 'in', self.partner_ids.ids))
            
        points_cond = []
        if self.check_earned:
            points_cond.append(('issued', '>', 0))
        if self.check_redeemed:
            points_cond.append(('used', '>', 0))
            
        if len(points_cond) == 1:
            domain.append(points_cond[0])
        elif len(points_cond) == 2:
            domain.append('|')
            domain.extend(points_cond)

        if not self.env['loyalty.history'].search_count(domain):
            raise ValidationError(_('No loyalty history records found for the selected date range and filters.'))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/loyalty_report/download?wizard_id={self.id}',
            'target': 'self',
        }
