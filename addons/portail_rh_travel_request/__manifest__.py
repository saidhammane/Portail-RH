{
    "name": "Portail RH Demandes de deplacement",
    "version": "17.0.1.0.0",
    "summary": "Gestion des demandes de deplacement et mission",
    "category": "Ressources humaines",
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
