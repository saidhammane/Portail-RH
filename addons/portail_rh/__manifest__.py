{
    "name": "Portail RH",
    "version": "17.0.1.2.0",
    "depends": ["base", "mail", "hr", "portal", "website"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/sequence.xml",
        "views/supply_request_views.xml",
        "views/menu.xml",
        "views/portal_templates.xml",
        "views/travel_dashboard_views.xml",
        "views/travel_request_views.xml",
    ],
    "demo": [
        "demo/hr_demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "portail_rh/static/src/js/user_menu_username.js",
        ],
    },
    "application": True,
    "license": "LGPL-3",
}

