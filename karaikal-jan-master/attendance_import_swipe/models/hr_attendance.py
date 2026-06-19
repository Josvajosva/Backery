from odoo import models, fields, api
import pytz
from datetime import timedelta
from pytz import timezone
from odoo.addons.resource.models.utils import Intervals
from collections import defaultdict


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    category = fields.Selection([
        ('factory', 'Factory'),
        ('general', 'General'),
        ('store', 'Store'),
    ], string="Category")

    # location = fields.Char(string="Location")
    location_id = fields.Many2one('hr.work.location', string="Location")

    days = fields.Float(
        string="Worked Days",
        compute="_compute_days",
        store=True,
        readonly=True
    )

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_days(self):
        for att in self:
            att.days = 0

            if not att.check_in or not att.check_out or not att.employee_id:
                continue

            employee = att.employee_id
            calendar = att._get_employee_calendar()
            if not calendar:
                continue

            tz = pytz.timezone(calendar.tz or employee._get_tz())

            check_in = att.check_in.astimezone(tz)
            check_out = att.check_out.astimezone(tz)

            current_day = check_in.date()
            end_day = check_out.date()

            total_days = 0

            while current_day <= end_day:
                day_start = tz.localize(fields.Datetime.to_datetime(current_day))
                day_end = day_start + timedelta(days=1)

                # intervals = calendar._attendance_intervals_batch(
                #     day_start,
                #     day_end,
                #     resources=employee.resource_id
                # ).get(employee.resource_id.id, [])
                # print('intervals', intervals)
                #
                # # if intervals:
                # #     print('intervals', intervals)
                real_start = max(check_in, day_start)
                real_end = min(check_out, day_end)

                worked_hours = max(
                    (real_end - real_start).total_seconds() / 3600.0,
                    0.0
                )

                if worked_hours > 0:
                    total_days += 1

                current_day += timedelta(days=1)

            att.days = total_days

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        """ Computes the worked hours of the attendance record.
            The worked hours of resource with flexible calendar is computed as the difference
            between check_in and check_out, without taking into account the lunch_interval"""
        for attendance in self:
            if attendance.check_out and attendance.check_in and attendance.employee_id:
                calendar = attendance._get_employee_calendar()
                resource = attendance.employee_id.resource_id
                tz = timezone(resource.tz) if not calendar else timezone(calendar.tz)
                check_in_tz = attendance.check_in.astimezone(tz)
                check_out_tz = attendance.check_out.astimezone(tz)
                lunch_intervals = []
                if not attendance.employee_id.is_flexible:
                    lunch_intervals = attendance.employee_id._employee_attendance_intervals(check_in_tz, check_out_tz,
                                                                                            lunch=True)
                attendance_intervals = Intervals([(check_in_tz, check_out_tz, attendance)]) - lunch_intervals
                delta = sum((i[1] - i[0]).total_seconds() for i in attendance_intervals)
                attendance.worked_hours = max(0.0, delta / 3600.0)
            else:
                attendance.worked_hours = False

    @api.depends(
        'employee_id',
        'employee_id.contract_id.resource_calendar_id',
        'overtime_status',
        'overtime_hours'
    )
    def _compute_validated_overtime_hours(self):
        for attendance in self:
            validated_ot = 0.0

            # 🔹 Get standard hours per day from contract calendar
            contract = attendance.employee_id.contract_id
            hours_per_day = (
                contract.resource_calendar_id.hours_per_day
                if contract and contract.resource_calendar_id
                else 0.0
            )

            # 🔹 Extra hours calculation
            extra_hours = max(0.0, attendance.overtime_hours - hours_per_day)

            # 🔹 Apply validation rules
            if attendance.employee_id.company_id.attendance_overtime_validation != 'no_validation':
                if attendance.overtime_status == 'to_approve':
                    validated_ot = extra_hours
                elif attendance.overtime_status == 'refused':
                    validated_ot = 0.0
            else:
                validated_ot = extra_hours

            attendance.validated_overtime_hours = validated_ot

    @api.depends('worked_hours')
    def _compute_overtime_hours(self):
        att_progress_values = dict()
        negative_overtime_attendances = defaultdict(lambda: False)
        if self.employee_id:
            self.env['hr.attendance'].flush_model(['worked_hours'])
            self.env['hr.attendance.overtime'].flush_model(['duration'])
            self.env.cr.execute('''
                    WITH employee_time_zones AS (
                        SELECT employee.id AS employee_id,
                               calendar.tz AS timezone
                          FROM hr_employee employee
                    INNER JOIN resource_calendar calendar
                            ON calendar.id = employee.resource_calendar_id
                    )
                    SELECT att.id AS att_id,
                           att.worked_hours AS att_wh,
                           ot.id AS ot_id,
                           ot.duration AS ot_d,
                           ot.date AS od,
                           att.check_in AS ad
                      FROM hr_attendance att
                INNER JOIN employee_time_zones etz
                        ON att.employee_id = etz.employee_id
                INNER JOIN hr_attendance_overtime ot
                        ON date_trunc('day',
                                      CAST(att.check_in
                                               AT TIME ZONE 'utc'
                                               AT TIME ZONE etz.timezone
                                      as date)) = date_trunc('day', ot.date)
                       AND att.employee_id = ot.employee_id
                       AND att.employee_id IN %s
                       AND ot.adjustment IS false
                  ORDER BY att.check_in DESC
                ''', (tuple(self.employee_id.ids),))
            a = self.env.cr.dictfetchall()
            grouped_dict = dict()
            for row in a:
                if row['ot_id'] and row['att_wh']:
                    if row['ot_id'] not in grouped_dict:
                        grouped_dict[row['ot_id']] = {'attendances': [(row['att_id'], row['att_wh'])],
                                                      'overtime_duration': row['ot_d']}
                    else:
                        grouped_dict[row['ot_id']]['attendances'].append((row['att_id'], row['att_wh']))

            for overtime in grouped_dict:
                overtime_reservoir = grouped_dict[overtime]['overtime_duration']
                if overtime_reservoir > 0:
                    for attendance in grouped_dict[overtime]['attendances']:
                        if overtime_reservoir > 0:
                            sub_time = attendance[1] - overtime_reservoir
                            if sub_time < 0:
                                att_progress_values[attendance[0]] = 0
                                overtime_reservoir -= attendance[1]
                            else:
                                att_progress_values[attendance[0]] = float(
                                    ((attendance[1] - overtime_reservoir) / attendance[1]) * 100)
                                overtime_reservoir = 0
                        else:
                            att_progress_values[attendance[0]] = 100
                elif overtime_reservoir < 0 and grouped_dict[overtime]['attendances']:
                    att_id = grouped_dict[overtime]['attendances'][0][0]
                    att_progress_values[att_id] = overtime_reservoir
                    negative_overtime_attendances[att_id] = True
        for attendance in self:
            # 🔹 Get hours_per_day from contract calendar
            contract = attendance.employee_id.contract_id
            hours_per_day = (
                contract.resource_calendar_id.hours_per_day
                if contract and contract.resource_calendar_id
                else 0.0
            )

            if negative_overtime_attendances[attendance.id]:
                attendance.overtime_hours = max(
                    0.0,
                    att_progress_values.get(attendance.id, 0)
                )
            else:
                # 🔹 Original percentage-based OT
                computed_ot = attendance.worked_hours * (
                        (100 - att_progress_values.get(attendance.id, 100)) / 100
                )

                # 🔹 Convert to "extra hours beyond hours_per_day"
                if hours_per_day:
                    attendance.overtime_hours = max(
                        0.0,
                        min(computed_ot, attendance.worked_hours - hours_per_day)
                    )
                else:
                    attendance.overtime_hours = max(0.0, computed_ot)


