# Portail RH - Odoo 17

Application RH pour Odoo 17 Community, livree avec Docker Compose et un simulateur ZKTeco local.

## Fonctionnalites

### Demandes RH

- Deplacements : creation, soumission, validation manager/RH, refus et cloture.
- Fournitures : creation, soumission, validation manager/RH, refus et cloture.
- Attestations : demande employe, validation RH et generation PDF securisee.
- Activites Odoo automatiques pour les validations manager.
- Champs sensibles verrouilles apres soumission.
- Etats modifiables uniquement par les actions du workflow.

### Portail employe

- Tableau de bord et compteurs personnels.
- Listes, filtres, tri et pagination.
- Creation et soumission depuis le portail.
- Detail de chaque demande.
- Telechargement d'une attestation approuvee au format PDF.
- Isolation stricte : un employe ne voit que ses propres demandes.

Routes principales :

- `/my/travel_requests`
- `/my/supply_requests`
- `/my/attestation_requests`

### Pointage ZKTeco

- Simulateur autonome avec une API protegee par cle.
- 9 employes et 383 pointages realistes pour juillet 2026.
- Import pagine et idempotent des pointages dans Odoo.
- Association automatique par identifiant ZKTeco ou adresse email.
- Conversion des paires entree/sortie en presences Odoo.
- Recuperation automatique lorsqu'une sortie arrive apres une entree deja signalee en erreur.
- Detection des retards et departs anticipes selon le calendrier de travail.
- Synchronisation manuelle ou planifiee par cron.

### Reporting et securite

- Tableau de bord pivot/graphique des deplacements.
- Profils Employe, Manager et RH.
- ACL et record rules pour chaque modele.
- Acces aux attestations PDF verifie cote serveur.
- Identifiants externes ZKTeco uniques par appareil.

## Architecture

```text
odoo-dev/
|-- addons/
|   `-- portail_rh/
|       |-- controllers/
|       |-- data/
|       |-- demo/
|       |-- migrations/
|       |-- models/
|       |-- reports/
|       |-- security/
|       |-- static/
|       |-- tests/
|       `-- views/
|-- services/
|   `-- zkteco_mock/
`-- docker-compose.yml
```

Stack : Odoo 17 Community, PostgreSQL 15, Python 3.12 pour le simulateur et Docker Compose.

Version du module : `17.0.1.8.0`.

## Demarrage

```powershell
docker compose up -d
```

Services :

- Odoo : `http://localhost:8069`
- PostgreSQL : `localhost:5432`
- Simulateur ZKTeco : `http://localhost:8090/demo`

Configuration ZKTeco par defaut :

- URL interne : `http://zkteco-mock:8090`
- Cle : `zkteco-demo-key`
- Fuseau horaire : `Africa/Casablanca`

Ces valeurs peuvent etre surchargees avec `ZKTECO_API_KEY`, `ZKTECO_SEED_MONTH` et `ZKTECO_TIMEZONE`.

## Installation ou mise a jour

Depuis l'interface Odoo, installer ou mettre a niveau l'application `Portail RH`.

Depuis Docker :

```powershell
docker compose exec -T odoo odoo -d odoo_dev -u portail_rh --db_host db --db_user odoo --db_password odoo --stop-after-init --no-http
```

## Donnees de demonstration

Le fichier `addons/portail_rh/demo/hr_demo_data.xml` fournit :

- 3 departements et leurs managers ;
- 6 employes et leurs utilisateurs ;
- 3 demandes de deplacement ;
- 3 demandes de fournitures ;
- 3 demandes d'attestation.

Mot de passe des utilisateurs de demonstration : `Test@1234`.

Le simulateur ZKTeco utilise les memes adresses email et associe les employes lors du premier import.

## Tests

### Tests du module Odoo

Le module contient des tests de workflow, securite, pointage, portail HTTP et rapport PDF.

```powershell
docker compose run --rm odoo odoo -d portail_rh_test -i portail_rh --without-demo=all --test-enable --test-tags /portail_rh --db_host db --db_user odoo --db_password odoo --stop-after-init --log-level=test
```

Pour relancer les tests sur une base deja initialisee, remplacer `-i` par `-u`.

### Tests du simulateur ZKTeco

```powershell
docker run --rm -v "${PWD}/services/zkteco_mock:/app" -w /app python:3.12-slim python -m unittest discover -s tests -v
```

## Verification de livraison

Avant une livraison :

1. Verifier que `docker compose ps` affiche les trois services actifs.
2. Mettre a niveau `portail_rh` sur la base cible.
3. Executer les tests Odoo et ZKTeco.
4. Tester une synchronisation ZKTeco sur une base de recette.
5. Verifier le telechargement d'une attestation approuvee.

La base `odoo_dev` est une base de developpement. Utiliser une sauvegarde PostgreSQL avant toute mise a niveau d'une base de production.
