/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class TeamKanbanDashboard extends Component {
    static template = "oi_helpdesk_dashboard.TeamKanbanDashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            teams: [],
        });
        onWillStart(async () => {
            try {
                const assignee = this.getAssigneeUidForRpc();
                const teams = await this.orm.call("helpdesk.team", "get_helpdesk_team_dashboard_cards", [
                    assignee,
                ]);
                this.state.teams = teams || [];
            } catch (e) {
                this.state.error = e.data?.message || e.message || String(e);
            } finally {
                this.state.loading = false;
            }
        });
    }

    /**
     * Context from server: explicit assignee (another user, unassigned, or uid from menu).
     * If the key is missing, default to logged-in user (main menu / safe fallback).
     */
    getAssigneeUidForRpc() {
        const ctx = this.props.action?.context || {};
        if (Object.prototype.hasOwnProperty.call(ctx, "helpdesk_dashboard_assignee_uid")) {
            const v = ctx.helpdesk_dashboard_assignee_uid;
            if (v === false || v === null) {
                return false;
            }
            const n = Number(v);
            return Number.isFinite(n) ? n : user.userId;
        }
        return user.userId;
    }

    onBack() {
        this.env.config?.historyBack?.();
    }

    openTicketList(name, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "helpdesk.ticket",
            view_mode: "list,kanban,form",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            domain,
            target: "current",
        });
    }

    /** @param {"open"|"unassigned"|"urgent"|"failed"} metric */
    openTeamMetricTickets(teamId, metric) {
        const assignee = this.getAssigneeUidForRpc();
        if (metric === "unassigned") {
            this.openTicketList("Unassigned tickets", [
                ["team_id", "=", teamId],
                ["user_id", "=", false],
                ["stage_id.fold", "=", false],
            ]);
            return;
        }
        const domain = [["team_id", "=", teamId]];
        if (assignee === false) {
            domain.push(["user_id", "=", false]);
        } else {
            domain.push(["user_id", "=", assignee]);
        }
        domain.push(["stage_id.fold", "=", false]);
        if (metric === "urgent") {
            domain.push(["priority", "=", "3"]);
        } else if (metric === "failed") {
            domain.push(["sla_fail", "=", true]);
        }
        const titles = {
            open: "Open tickets",
            urgent: "Urgent tickets",
            failed: "Failed SLA tickets",
        };
        this.openTicketList(titles[metric] || "Tickets", domain);
    }

    openTeamOpenTickets(teamId) {
        this.openTeamMetricTickets(teamId, "open");
    }
}
