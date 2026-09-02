# Portail RH - Odoo 17

Application RH Odoo 17 Community avec portail employe, workflows de demandes, pointage ZKTeco et assistant d'integration RAG securise.

## Fonctionnalites

- Deplacements, fournitures et attestations PDF avec workflows Employe / Manager / RH.
- Portail natif Odoo, isolation des employes, formulaires et telechargements controles cote serveur.
- Simulateur ZKTeco, import idempotent vers `hr.attendance`, retards et departs anticipes.
- Documents d'integration PDF, DOCX et TXT administres par RH.
- Indexation asynchrone Redis vers Qdrant avec verrou de deduplication.
- Assistant cite : chaque reponse acceptee contient des sources autorisees.
- Refus explicite et proposition d'escalade RH lorsque les sources sont insuffisantes.
- Checklist personnalisee par departement et poste.
- Cache, sessions avec TTL et rate limiting dans Redis.

Routes portail principales :

- `/my/travel_requests`
- `/my/supply_requests`
- `/my/attestation_requests`
- `/my/onboarding`
- `/my/onboarding/checklist`

## Architecture

```text
Navigateur
   |
   v
Odoo 17 + PostgreSQL  ---- post-commit ----> FastAPI ----> Redis queue
   ^                         chat serveur       |              |
   |                                            v              v
   +------ callback authentifie <----------- Qdrant <------ Worker
                                                   embeddings / extraction
```

Odoo reste la source de verite pour les utilisateurs, roles, documents, conversations, feedbacks et checklists. Redis ne contient que des donnees ephemeres. Qdrant n'est pas expose sur l'hote et chaque recherche applique des filtres societe, departement et visibilite. Odoo recontrole ensuite les sources avant de les enregistrer ou de les afficher.

Voir [docs/ai-onboarding-architecture.md](docs/ai-onboarding-architecture.md) pour les flux et le modele de securite.

Version du module : `17.0.2.1.0`.

## Configuration locale

```powershell
Copy-Item .env.example .env
```

Renseigner au minimum dans `.env` :

- `POSTGRES_PASSWORD`
- `ZKTECO_API_KEY`
- `ONBOARDING_AI_SERVICE_TOKEN` (16 caracteres minimum)
- `ODOO_DATABASE`

Le fichier `.env` est ignore par Git. `PORTAIL_RH_DEMO_PASSWORD` est facultatif. Lorsqu'il est defini, l'installation initialise automatiquement la demonstration Bravico complete : logo officiel, identite legale, 13 collaborateurs, coordonnees, departements, documents internes, checklists et comptes de test. Aucun mot de passe de demonstration n'est versionne.

Le provider par defaut est maintenant le vrai modele generatif local `qwen2.5:0.5b`, execute par Ollama. Ce modele compact privilegie une reponse interactive sur CPU et ne demande aucune cle externe : les questions et documents restent dans la pile Docker locale. Le premier demarrage telecharge et precharge automatiquement le modele avant d'ouvrir l'API. Les reponses sont generees avec historique de conversation, contraintes par les documents autorises et accompagnees de citations.

Providers pris en charge :

- `ollama` (defaut) : generation locale avec Qwen et recherche locale `hashing-128` ;
- `extractive` : ancien mode deterministe sans generation, conserve pour les tests et le diagnostic ;
- `openai` compatible : definir `LLM_PROVIDER=openai`, l'URL, les modeles et `LLM_API_KEY`.

Les cles ne sont jamais journalisees.

## Demarrage Docker

```powershell
docker compose up -d --build
docker compose ps
```

Services publies localement :

- Odoo : `http://localhost:8069`
- API onboarding : `http://127.0.0.1:8088`
- Ollama : `http://127.0.0.1:11434`
- PostgreSQL : `127.0.0.1:5432`
- ZKTeco : `http://127.0.0.1:8090/demo`

Redis et Qdrant restent uniquement sur le reseau Compose.

Verification :

```powershell
Invoke-RestMethod http://127.0.0.1:8088/health
Invoke-RestMethod http://127.0.0.1:8088/ready
docker compose exec -T redis redis-cli ping
```

## Installation et mise a niveau Odoo

Installer `Portail RH` depuis Apps ou executer :

```powershell
docker compose run --rm odoo odoo -d $env:ODOO_DATABASE -i portail_rh --db_host db --db_user odoo --db_password "$env:POSTGRES_PASSWORD" --stop-after-init --no-http
```

Pour une mise a niveau, remplacer `-i` par `-u`. Sauvegarder la base cible avant toute mise a niveau hors developpement.

## Scenario de demonstration

1. Se connecter comme RH et ouvrir `Portail RH > Integration > Documents`.
2. Charger un PDF textuel, DOCX ou TXT, choisir societe, departement et visibilite.
3. Attendre l'etat `Indexe` ; le worker met a jour Odoo par callback authentifie.
4. Creer un plan et ses etapes dans `Integration > Plans`.
5. Se connecter comme employe et ouvrir `/my/onboarding`.
6. Poser une question couverte : la reponse affiche `[1]` et la source.
7. Poser une question inconnue : l'assistant refuse et propose `Transmettre a RH`.
8. Verifier la checklist et les liens rapides vers les trois demandes RH.

## Tests

Tests Odoo complets :

```powershell
docker compose run --rm odoo odoo -d portail_rh_test -i portail_rh --without-demo=all --test-enable --test-tags /portail_rh --db_host db --db_user odoo --db_password "$env:POSTGRES_PASSWORD" --stop-after-init --log-level=test
```

Tests et evaluation du service IA :

```powershell
docker compose build onboarding-ai-api
docker run --rm portail-rh-onboarding-ai:local python -m pytest -q
docker run --rm portail-rh-onboarding-ai:local python -m evaluation.run_evaluation
```

Tests ZKTeco :

```powershell
docker run --rm -v "${PWD}/services/zkteco_mock:/app" -w /app python:3.12-slim python -m unittest discover -s tests -v
```

Baseline deterministe actuelle sur 30 questions : citations correctes 95,65 %, refus corrects 100 %, exactitude globale 96,67 %, cache 50 % sur deux passages. Ces mesures valident le dataset local ; elles ne constituent pas une garantie de qualite sur des documents reels ou un provider externe.

## Kubernetes

Les manifests sont sous `deploy/k8s` et se valident avec :

```powershell
kubectl kustomize deploy/k8s
```

Avant un deploiement, remplacer le tag d'image, provisionner un stockage `ReadWriteMany` pour les fichiers de jobs, adapter `ODOO_CALLBACK_URL`, et creer `onboarding-ai-secrets` avec un gestionnaire de secrets. `secret.example.yaml` ne contient aucune valeur reelle et n'est pas inclus automatiquement par Kustomize.

Ces manifests ont ete rendus et valides syntaxiquement, mais pas testes sur un cluster cible ; ils ne sont donc pas declares production-ready.

## Limites

- Pas d'OCR : les PDF scannes sans couche texte sont refuses.
- La recherche locale `hashing-128` exige un recouvrement lexical ; le modele generatif reformule ensuite naturellement les passages trouves.
- La qualite des reponses depend du modele, des documents autorises et du seuil configure. En l'absence de source suffisante, l'assistant refuse et propose une escalade RH.
- Qdrant est deploye en instance unique dans les exemples Docker/Kubernetes.
- Le PVC de jobs Kubernetes exige une classe de stockage RWX compatible.
- La retention des conversations reste geree dans PostgreSQL/Odoo et doit suivre la politique de confidentialite de l'organisation.
