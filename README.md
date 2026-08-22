# Portail RH - Odoo 17

Projet Odoo 17 Community avec un seul module custom : `addons/portail_rh`.

Le depot contient aussi un simulateur ZKTeco autonome dans `services/zkteco_mock`. Il fournit une API locale et un mois de pointages realistes pour tester une future synchronisation avec Odoo.

## Apercu

Ce projet fournit un mini portail RH avec :
- demandes de deplacement
- demandes de fournitures
- workflow employe / manager / RH
- tableau de bord des deplacements
- portail web employe pour consulter, creer et soumettre ses demandes

## Stack technique

- Odoo 17 Community
- PostgreSQL 15
- Docker Compose

## Structure du projet

```text
odoo-dev/
|-- addons/
|   `-- portail_rh/
|       |-- controllers/
|       |-- data/
|       |-- demo/
|       |-- migrations/
|       |-- models/
|       |-- security/
|       |-- static/
|       `-- views/
`-- docker-compose.yml
```

## Module custom

Nom du module :
- `Portail RH`

Chemin :
- `addons/portail_rh`

Version actuelle :
- `17.0.1.2.0`

Dependances :
- `base`
- `mail`
- `hr`
- `portal`
- `website`

## Fonctionnalites principales

### 1. Demandes de deplacement

Modele :
- `hr.travel.request`

Fonctionnalites :
- creation d'une demande
- etats : `draft`, `submitted`, `approved`, `rejected`, `done`
- validation par manager ou RH
- protection des modifications apres soumission
- activite manager lors de la soumission

Champs principaux :
- employe
- departement
- manager
- destination
- date debut
- date fin
- duree
- cout estime
- motif
- etat

### 2. Demandes de fournitures

Modele :
- `hr.supply.request`

Fonctionnalites :
- creation d'une demande
- etats : `draft`, `submitted`, `approved`, `rejected`, `done`
- validation par manager ou RH
- activite manager lors de la soumission

Champs principaux :
- employe
- departement
- manager
- article
- description
- quantite
- cout estime
- motif
- etat

### 3. Tableau de bord

Modele report :
- `hr.travel.request.report`

Fonctionnalites :
- vue pivot
- vue graph
- filtres par periode
- filtres par etat
- indicateurs de cout et volume

### 4. Portail web employe

Routes principales :
- `/my/home`
- `/my/travel_requests`
- `/my/travel_requests/new`
- `/my/supply_requests`
- `/my/supply_requests/new`

Regle de securite :
- un employe ne voit que ses propres demandes
- filtrage base sur `employee_id.user_id = user.id`

## Securite

Groupes utilises :
- `portail_rh.group_portail_rh_employee`
- `portail_rh.group_portail_rh_manager`
- `portail_rh.group_portail_rh_hr`

Les ACL et record rules couvrent :
- demandes de deplacement
- demandes de fournitures
- tableau de bord deplacement

## Lancer le projet

Depuis la racine du projet :

```powershell
docker compose up -d
```

Acces Odoo :
- `http://localhost:8069`

Base PostgreSQL :
- host : `localhost`
- port : `5432`
- user : `odoo`
- password : `odoo`

Simulateur ZKTeco :
- API : `http://localhost:8090`
- cle locale par defaut : `zkteco-demo-key`
- donnees : juillet 2026, 9 employes, pointages entree/sortie
- documentation : `services/zkteco_mock/README.md`

## Installer ou mettre a jour le module

Depuis l'interface Odoo :
1. Ouvrir `Apps`
2. Rechercher `Portail RH`
3. Cliquer sur `Installer` ou `Mettre a niveau`

Depuis Docker :

```powershell
docker compose exec -T odoo odoo -d odoo_dev -u portail_rh --db_host db --db_user odoo --db_password odoo --stop-after-init
```

## Donnees de demo

Les donnees de demo sont dans :
- `addons/portail_rh/demo/hr_demo_data.xml`

Elles sont chargees uniquement si la base est creee avec les donnees de demo activees.

Contenu demo :
- 3 departements
- managers
- employes
- utilisateurs de test
- demandes de deplacement
- demandes de fournitures

Mot de passe demo :

```text
Test@1234
```

## Fichiers importants

Modeles :
- `addons/portail_rh/models/travel_request.py`
- `addons/portail_rh/models/supply_request.py`
- `addons/portail_rh/models/travel_dashboard.py`

Controleurs :
- `addons/portail_rh/controllers/portal.py`

Securite :
- `addons/portail_rh/security/security.xml`
- `addons/portail_rh/security/ir.model.access.csv`
- `addons/portail_rh/security/rules.xml`

Vues :
- `addons/portail_rh/views/menu.xml`
- `addons/portail_rh/views/travel_request_views.xml`
- `addons/portail_rh/views/supply_request_views.xml`
- `addons/portail_rh/views/travel_dashboard_views.xml`
- `addons/portail_rh/views/portal_templates.xml`

## Verifications conseillees

Back-office :
- l'app `Portail RH` apparait dans le lanceur
- le menu `Deplacements` fonctionne
- le menu `Fournitures` fonctionne
- les droits changent selon le role

Portail :
- `/my/home`
- `/my/travel_requests`
- `/my/travel_requests/new`
- `/my/supply_requests`
- `/my/supply_requests/new`

Donnees :
- un employe ne voit que ses propres demandes
- un manager traite les demandes de son equipe
- RH voit tout

## Resume

Ce depot est volontairement simple :
- un seul module custom
- backend + portail web
- workflows RH de base
- Docker pour le lancement local

Prochaines extensions possibles :
- pieces jointes
- notifications email
- impression PDF
- workflow multi-niveaux
- dashboards plus riches
