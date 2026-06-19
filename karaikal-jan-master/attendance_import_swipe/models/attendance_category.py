from odoo import models, fields

class HrAttendanceCategory(models.Model):
    _name = 'hr.attendance.category'
    _description = 'Attendance Category Configuration'
    _rec_name = 'name'

    name = fields.Char(required=True)
    code = fields.Selection([
        ('general', 'General'),
        ('factory', 'Factory'),
        ('store', 'Store'),
    ], required=True, string='Category')

    standard_hours = fields.Float(
        string='Standard Working Hours / Day',
        required=True,
        help="Hours beyond this will be counted as overtime"
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('uniq_category_company',
         'unique(code, company_id)',
         'Each category must be unique per company!')
    ]


class WorkLocation(models.Model):
    _name = 'work.location'

    name = fields.Char(required=True, string='Name', tracking=True)
    code = fields.Char(required=True, string='Code', tracking=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    category = fields.Selection([
        ('factory', 'Factory'),
        ('general', 'General'),
        ('store', 'Store'),
    ], string="Category")
