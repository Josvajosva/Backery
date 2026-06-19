from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    dp_code = fields.Char(string="Department Code")

