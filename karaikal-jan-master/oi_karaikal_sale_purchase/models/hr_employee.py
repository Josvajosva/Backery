from odoo import models,fields,api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pos_user = fields.Boolean("Pos User", default=False)

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    pos_user = fields.Boolean("Pos User", default=False)
