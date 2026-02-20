{
    "name": "Portail RH Travel Request",
    "version": "17.0.1.0.0",
    "summary": "Manage employee travel and mission requests",
    "category": "Human Resources",
    "depends": ["base", "mail", "hr"],
    "data": [
        "security/security.xml",
        "security/rules.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/travel_request_views.xml",
        "views/menu.xml",
    ],
    "application": True,
    "license": "LGPL-3",
}
