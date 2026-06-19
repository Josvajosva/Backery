/** @odoo-module **/
import { registry } from "@web/core/registry";
import { UserWiseDashboard } from "./user_wise_dashboard_action";
import { TeamKanbanDashboard } from "./team_kanban_dashboard";

registry.category("actions").add("oi_helpdesk_dashboard_user_wise", UserWiseDashboard);
registry.category("actions").add("oi_helpdesk_dashboard_team_kanban", TeamKanbanDashboard);
