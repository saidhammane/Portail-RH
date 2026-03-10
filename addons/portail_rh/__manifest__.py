{
    "name": "Portail RH",
    "version": "17.0.1.0.0",
    "depends": ["base", "mail", "hr"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/sequence.xml",
        "data/hr_seed_data.xml",
        "views/supply_request_views.xml",
        "views/menu.xml",
        "views/travel_dashboard_views.xml",
        "views/travel_request_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "portail_rh/static/src/js/user_menu_username.js",
        ],
    },
    "application": True,
    "license": "LGPL-3",
}
