# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import AccessError


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model
    def get_director_user_wise_dashboard(self):
        if not self.env.user.has_group("oi_helpdesk_dashboard.group_helpdesk_director"):
            raise AccessError(_("Only Helpdesk Directors can open this dashboard."))

        rows_raw = self._read_group(
            [("stage_id.fold", "=", False)],
            ["user_id"],
            ["__count"],
        )
        rows_raw.sort(key=lambda item: item[1], reverse=True)

        current_uid = self.env.user.id
        total_all = sum(int(c) for __, c in rows_raw)
        my_open_count = 0
        lines = []
        for user, count in rows_raw:
            cnt = int(count)
            if user and user.id == current_uid:
                my_open_count = cnt
                continue
            if user:
                lines.append(
                    {
                        "user_id": user.id,
                        "user_name": user.sudo().display_name,
                        "ticket_count": cnt,
                    }
                )
            # Unassigned open tickets are excluded from this table (see team Kanban for per-team unassigned).

        return {
            "total": total_all,
            "current_user_id": current_uid,
            "my_open_count": my_open_count,
            "rows": lines,
        }
