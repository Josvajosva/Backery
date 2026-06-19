from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AttendanceLocationWizard(models.TransientModel):
    _name = "attendance.location.wizard"
    _description = "Attendance Location Wizard"

    date_from = fields.Date(
        string="Date From",
        required=True
    )
    date_to = fields.Date(
        string="Date To",
        required=True
    )

    location_ids = fields.Many2many(
        "hr.work.location",
        string="Work Locations",
        required=False
    )

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(
                    _("From Date cannot be later than To Date.")
                )

    def action_print_excel(self):
        self.ensure_one()

        return {
            "type": "ir.actions.report",
            "report_name": "attendance_import_swipe.attendance_excel_xlsx",
            "report_type": "xlsx",
            "data": {
                "date_from": self.date_from.strftime("%Y-%m-%d"),
                "date_to": self.date_to.strftime("%Y-%m-%d"),
                "location_ids": self.location_ids.ids,
            },
        }
