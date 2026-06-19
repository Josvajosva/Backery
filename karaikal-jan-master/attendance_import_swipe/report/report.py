from odoo import models, fields, _
from datetime import datetime, time
import calendar
from odoo.exceptions import ValidationError


class AttendanceExcelXlsx(models.AbstractModel):
    _name = "report.attendance_import_swipe.attendance_excel_xlsx"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, docs):

        # ================= FORMATS =================
        title_format = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "align": "center",
        })

        label_format = workbook.add_format({
            "bold": True,
            "align": "left",
        })

        value_format = workbook.add_format({
            "align": "left",
        })

        header = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#E7F3FF",
        })

        text_cell = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })

        number_cell = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })

        location_header = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "left",
            "bg_color": "#D9D9D9",
        })

        total_format = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "center",
        })

        total_format_name = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "center",
        })

        # ================= FILTER DATA =================
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        location_ids = data.get("location_ids")

        domain = [
            ("employee_id.barcode", "!=", False),
            ("check_in", "!=", False),
        ]

        if date_from:
            domain.append(("check_in", ">=", datetime.combine(
                fields.Date.from_string(date_from), time.min)))

        if date_to:
            domain.append(("check_in", "<=", datetime.combine(
                fields.Date.from_string(date_to), time.max)))

        if location_ids:
            domain += [
                "|",
                ("location_id", "=", False),
                ("location_id", "in", location_ids),
            ]

        attendances = self.env["hr.attendance"].search(domain)
        if not attendances:
            raise ValidationError(_("No attendances found for the selected filters."))

        months = sorted({
            (att.check_in.year, att.check_in.month)
            for att in attendances
        })

        # ================= EXCEL SHEETS =================
        for year, month in months:
            sheet_name = f"{calendar.month_name[month]} {year}"
            sheet = workbook.add_worksheet(sheet_name[:31])

            sheet.set_column("A:A", 25)
            sheet.set_column("B:B", 15)
            sheet.set_column("C:E", 15)
            sheet.set_column("F:G", 18)

            # ================= REPORT HEADER =================
            sheet.merge_range("A1:G1", "EMPLOYEE ATTENDANCE SUMMARY", title_format)

            sheet.write("A3", "Company :", label_format)
            sheet.write("B3", self.env.company.name, value_format)

            sheet.write("D3", "Month :", label_format)
            sheet.write("E3", sheet_name, value_format)

            sheet.write("A4", "Date From :", label_format)
            sheet.write("B4", date_from or "-", value_format)

            sheet.write("D4", "Date To :", label_format)
            sheet.write("E4", date_to or "-", value_format)

            locations_label = "All Locations"
            if location_ids:
                locations_label = ", ".join(
                    self.env["hr.work.location"].browse(location_ids).mapped("name")
                )

            sheet.write("A5", "Locations :", label_format)
            sheet.merge_range("B5:G5", locations_label, value_format)

            # ================= TABLE HEADER =================
            headers = [
                "Employee Name",
                "Employee ID",
                "Worked Hours",
                "Extra Hours",
                "Worked Days",
                "Category",
                "Location",
            ]

            row = 7
            for col, h in enumerate(headers):
                sheet.write(row, col, h, header)

            sheet.freeze_panes(row + 1, 0)
            row += 1

            start_date = datetime(year, month, 1)
            end_date = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)

            month_atts = attendances.filtered(
                lambda a: start_date <= a.check_in <= end_date
            )

            grand_wh = grand_ex = grand_days = 0.0

            locations = month_atts.mapped("location_id")
            locations |= self.env["hr.work.location"]

            for location in locations:
                location_atts = month_atts.filtered(lambda a: a.location_id == location)
                location_name = location.name if location else "Unassigned"

                sheet.merge_range(row, 0, row, 6,
                                  f"Location : {location_name}", location_header)
                row += 1

                loc_wh = loc_ex = loc_days = 0.0

                for emp in location_atts.mapped("employee_id"):
                    emp_atts = location_atts.filtered(lambda a: a.employee_id == emp)

                    worked_hours = sum(emp_atts.mapped("worked_hours"))
                    worked_days = sum(emp_atts.mapped("days"))

                    calendar_emp = emp.resource_calendar_id
                    planned_hours = calendar_emp.hours_per_day if calendar_emp else 8.0

                    extra_hours = max(worked_hours - (worked_days * planned_hours), 0.0)

                    last_att = emp_atts[-1]
                    category_label = dict(
                        last_att._fields["category"].selection
                    ).get(last_att.category, "")

                    sheet.write(row, 0, emp.name or "", text_cell)
                    sheet.write(row, 1, emp.barcode or "", text_cell)
                    sheet.write(row, 2, round(worked_hours, 2), number_cell)
                    sheet.write(row, 3, round(extra_hours, 2), number_cell)
                    sheet.write(row, 4, round(worked_days, 2), number_cell)
                    sheet.write(row, 5, category_label, text_cell)
                    sheet.write(row, 6, location_name, text_cell)

                    row += 1

                    loc_wh += worked_hours
                    loc_ex += extra_hours
                    loc_days += worked_days

                sheet.merge_range(row, 0, row, 1,
                                  f"TOTAL ({location_name})", total_format_name)
                sheet.write(row, 2, round(loc_wh, 2), total_format)
                sheet.write(row, 3, round(loc_ex, 2), total_format)
                sheet.write(row, 4, round(loc_days, 2), total_format)
                sheet.write(row, 5, "", total_format)
                sheet.write(row, 6, "", total_format)
                row += 1

                grand_wh += loc_wh
                grand_ex += loc_ex
                grand_days += loc_days

            sheet.merge_range(row, 0, row, 1, "GRAND TOTAL", total_format_name)
            sheet.write(row, 2, round(grand_wh, 2), total_format)
            sheet.write(row, 3, round(grand_ex, 2), total_format)
            sheet.write(row, 4, round(grand_days, 2), total_format)
            sheet.write(row, 5, "", total_format)
            sheet.write(row, 6, "", total_format)
