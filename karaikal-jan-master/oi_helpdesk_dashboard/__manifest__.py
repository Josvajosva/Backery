{
    "name": "Helpdesk Management Dashboard",
    "summary": "Helpdesk dashboard for managing tickets with WhatsApp support",
    "description": """
        A simplified Helpdesk Management Dashboard module focused on
        ticket handling based on the user.
    """,
    "version": "18.0.1.1.9",
    "license": "AGPL-3",
    "author": "Josva",
    "depends": ["helpdesk"],
    "data": [
        "security/helpdesk_dashboard_security.xml",
        "views/helpdesk_dashboard_menu.xml",
    ],
    "application": True,
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "oi_helpdesk_dashboard/static/src/scss/user_wise_dashboard.scss",
            "oi_helpdesk_dashboard/static/src/scss/team_kanban_dashboard.scss",
            "oi_helpdesk_dashboard/static/src/xml/user_wise_dashboard_action.xml",
            "oi_helpdesk_dashboard/static/src/xml/team_kanban_dashboard.xml",
            "oi_helpdesk_dashboard/static/src/js/user_wise_dashboard_action.js",
            "oi_helpdesk_dashboard/static/src/js/team_kanban_dashboard.js",
            "oi_helpdesk_dashboard/static/src/js/helpdesk_dashboard_client_actions.js",
        ],
    },
}