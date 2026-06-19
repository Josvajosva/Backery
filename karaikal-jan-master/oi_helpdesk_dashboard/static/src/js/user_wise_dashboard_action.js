/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function openTicketsAction(actionService, name, domain) {
    actionService.doAction({
        type: "ir.actions.act_window",
        name,
        res_model: "helpdesk.ticket",
        view_mode: "list,kanban,form,activity",
        views: [
            [false, "list"],
            [false, "kanban"],
            [false, "form"],
            [false, "activity"],
        ],
        domain,
        context: {},
        target: "current",
    });
}

export class UserWiseDashboard extends Component {
    static template = "oi_helpdesk_dashboard.UserWiseDashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            total: 0,
            myOpenCount: 0,
            currentUserId: null,
            rows: [],
        });
        onWillStart(async () => {
            try {
                const data = await this.orm.call("helpdesk.ticket", "get_director_user_wise_dashboard", []);
                this.state.total = data.total;
                this.state.myOpenCount = data.my_open_count;
                this.state.currentUserId = data.current_user_id;
                this.state.rows = data.rows;
            } catch (e) {
                this.state.error = e.data?.message || e.message || String(e);
            } finally {
                this.state.loading = false;
            }
        });
    }

    openOpenTicketsDomain(name, extraDomain) {
        const base = [["stage_id.fold", "=", false]];
        const domain = extraDomain.length ? [...extraDomain, ...base] : base;
        openTicketsAction(this.action, name, domain);
    }

    onViewMoreAllOpen() {
        this.openOpenTicketsDomain("Open tickets", []);
    }

    onViewMoreMyTickets() {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "oi_helpdesk_dashboard_team_kanban",
            name: "My tickets",
            context: {
                helpdesk_dashboard_assignee_uid: this.state.currentUserId,
            },
            target: "current",
        });
    }

    onViewMoreForAssignee(row) {
        const title = `${row.user_name || "Tickets"} — teams`;
        const assigneeUid = row.user_id === false || row.user_id === null ? false : row.user_id;
        this.action.doAction({
            type: "ir.actions.client",
            tag: "oi_helpdesk_dashboard_team_kanban",
            name: title,
            context: {
                helpdesk_dashboard_assignee_uid: assigneeUid,
            },
            target: "current",
        });
    }

    onKpiKeydown(ev, kind) {
        if (ev.key !== "Enter" && ev.key !== " ") {
            return;
        }
        ev.preventDefault();
        if (kind === "total") {
            this.onViewMoreAllOpen();
        } else if (kind === "mine") {
            this.onViewMoreMyTickets();
        }
    }
}
