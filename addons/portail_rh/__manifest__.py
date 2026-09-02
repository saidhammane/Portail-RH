{
    "name": "Portail RH",
    "version": "17.0.2.1.0",
    "depends": ["base", "mail", "hr", "hr_attendance", "portal", "website"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/sequence.xml",
        "data/attendance_cron.xml",
        "reports/attestation_report.xml",
        "views/travel_request_views.xml",
        "views/supply_request_views.xml",
        "views/attestation_request_views.xml",
        "views/onboarding_views.xml",
        "views/menu.xml",
        "views/attendance_log_views.xml",
        "views/portal_templates.xml",
        "views/travel_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "portail_rh/static/src/js/user_menu_username.js",
        ],
        "web.assets_frontend": [
            "portail_rh/static/src/scss/bravico_portal.scss",
            "portail_rh/static/src/js/bravico_chat.js",
        ],
    },
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}

