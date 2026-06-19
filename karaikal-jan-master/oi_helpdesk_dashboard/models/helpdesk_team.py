# -*- coding: utf-8 -*-

import datetime

from dateutil import relativedelta

from odoo import api, models, _
from odoo.exceptions import AccessError


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    @api.model
    def _helpdesk_dashboard_teams_for_scope(self, assignee_uid, dt):
        Ticket = self.env["helpdesk.ticket"]
        if assignee_uid is False:
            return self.search([], order="sequence, name")
        relevant_ids = set()
        for team_rec, __ in Ticket._read_group(
            [
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", False),
            ],
            ["team_id"],
            ["__count"],
        ):
            if team_rec:
                relevant_ids.add(team_rec.id)
        for team_rec, __ in Ticket._read_group(
            [
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", True),
                ("close_date", ">=", dt),
            ],
            ["team_id"],
            ["__count"],
        ):
            if team_rec:
                relevant_ids.add(team_rec.id)
        if not relevant_ids:
            return self.browse()
        return self.search([("id", "in", list(relevant_ids))], order="sequence, name")

    @api.model
    def get_helpdesk_team_dashboard_cards(self, assignee_uid):
        user = self.env.user
        if not user.has_group("helpdesk.group_helpdesk_user"):
            raise AccessError(_("You must be a helpdesk user."))

        if assignee_uid is None:
            raise AccessError(_("Invalid dashboard request."))

        if assignee_uid is not False:
            try:
                assignee_uid = int(assignee_uid)
            except (TypeError, ValueError) as e:
                raise AccessError(_("Invalid user.")) from e
            if assignee_uid <= 0:
                raise AccessError(_("Invalid user."))

        is_director = user.has_group("oi_helpdesk_dashboard.group_helpdesk_director")

        if assignee_uid is False:
            if not is_director:
                raise AccessError(_("Only Helpdesk Directors can open the unassigned overview."))
        elif assignee_uid != user.id and not is_director:
            raise AccessError(_("You can only open your own ticket overview."))
        elif assignee_uid is not False and assignee_uid != user.id:
            if not self.env["res.users"].browse(assignee_uid).exists():
                raise AccessError(_("Invalid user."))

        dt = datetime.datetime.combine(
            datetime.date.today() - relativedelta.relativedelta(days=6),
            datetime.time.min,
        )
        Ticket = self.env["helpdesk.ticket"]

        def counts_map(domain):
            rows = Ticket._read_group(domain, ["team_id"], ["__count"])
            return {t.id: int(c) for t, c in rows}

        teams = self._helpdesk_dashboard_teams_for_scope(assignee_uid, dt)

        if not teams:
            return []

        team_ids = teams.ids

        if assignee_uid is False:
            base_open = [
                ("team_id", "in", team_ids),
                ("user_id", "=", False),
                ("stage_id.fold", "=", False),
            ]
            open_map = counts_map(base_open)
            urgent_map = counts_map(base_open + [("priority", "=", "3")])
            failed_map = counts_map(base_open + [("sla_fail", "=", True)])
            closed_map = counts_map(
                [
                    ("team_id", "in", team_ids),
                    ("user_id", "=", False),
                    ("stage_id.fold", "=", True),
                    ("close_date", ">=", dt),
                ]
            )
            out = []
            for team in teams:
                tid = team.id
                o = open_map.get(tid, 0)
                out.append(
                    {
                        "id": tid,
                        "name": team.name or "",
                        "alias_email": team.alias_email or "",
                        "open": o,
                        "unassigned": o,
                        "urgent": urgent_map.get(tid, 0),
                        "failed": failed_map.get(tid, 0),
                        "closed": closed_map.get(tid, 0),
                    }
                )
            return out

        unassigned_map = counts_map(
            [
                ("team_id", "in", team_ids),
                ("user_id", "=", False),
                ("stage_id.fold", "=", False),
            ]
        )
        open_map = counts_map(
            [
                ("team_id", "in", team_ids),
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", False),
            ]
        )
        urgent_map = counts_map(
            [
                ("team_id", "in", team_ids),
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", False),
                ("priority", "=", "3"),
            ]
        )
        failed_map = counts_map(
            [
                ("team_id", "in", team_ids),
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", False),
                ("sla_fail", "=", True),
            ]
        )
        closed_map = counts_map(
            [
                ("team_id", "in", team_ids),
                ("user_id", "=", assignee_uid),
                ("stage_id.fold", "=", True),
                ("close_date", ">=", dt),
            ]
        )

        out = []
        for team in teams:
            tid = team.id
            out.append(
                {
                    "id": tid,
                    "name": team.name or "",
                    "alias_email": team.alias_email or "",
                    "open": open_map.get(tid, 0),
                    "unassigned": unassigned_map.get(tid, 0),
                    "urgent": urgent_map.get(tid, 0),
                    "failed": failed_map.get(tid, 0),
                    "closed": closed_map.get(tid, 0),
                }
            )
        return out
