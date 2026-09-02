# Architecture de l'assistant d'integration

## Objectif et principes

L'assistant repond uniquement a partir de documents d'integration autorises. Une reponse sans source n'est pas consideree fiable : le service retourne un refus explicite et signale qu'une escalation RH est possible.

- Odoo est la source de verite metier et d'autorisation.
- Le navigateur ne communique jamais directement avec FastAPI.
- Les scopes sont calcules par Odoo a partir des groupes du compte authentifie.
- FastAPI et le callback Odoo partagent un jeton de service fourni par l'environnement.
- Redis est ephemere ; PostgreSQL conserve les conversations et checklists.
- Qdrant contient des chunks et metadonnees minimales, pas les comptes utilisateurs.
- Les sources sont filtrees dans Qdrant, post-filtrees dans FastAPI, puis revalidees dans Odoo.

## Composants

| Composant | Responsabilite | Donnees durables |
|---|---|---|
| Odoo `portail_rh` | documents, roles, conversations, feedback, checklist, portail | PostgreSQL et filestore |
| FastAPI | validation, rate limit, retrieval, generation/refus, citations | aucune |
| Worker Python | extraction, chunking, embeddings et indexation | aucune hors jobs temporaires |
| Redis | queue, verrou, cache, sessions TTL, rate limit, version documentaire | donnees reconstructibles |
| Qdrant | vecteurs et payloads de chunks | volume Qdrant |

## Flux d'indexation

1. RH charge un PDF textuel, DOCX ou TXT dans `hr.onboarding.document`.
2. Odoo calcule le SHA-256 et place le document en `pending`.
3. Apres commit PostgreSQL, Odoo envoie contenu et metadonnees a `POST /v1/index/jobs`.
4. FastAPI verifie jeton, taille, encodage et extension, ecrit un fichier temporaire puis pousse l'identifiant dans Redis.
5. Le worker prend un verrou Redis `company + checksum`.
6. Le texte est extrait sans OCR, normalise et decoupe en chunks chevauchants.
7. Le provider calcule les embeddings et le worker indexe Qdrant.
8. Chaque chunk contient document, titre, categorie, societe, departement, visibilite, version, checksum, index et texte.
9. Le worker incremente la version documentaire Redis, supprime le job et appelle Odoo.
10. Odoo accepte le callback uniquement si le jeton et le checksum courant correspondent.

Un marqueur `document + version + checksum` et un verrou Redis evitent la double indexation. Une nouvelle version invalide le cache de chat.

## Flux RAG

1. L'employe envoie une question avec CSRF a `/my/onboarding/ask`.
2. Odoo recupere l'employe courant et calcule les scopes `employee`, `manager`, `hr`.
3. Odoo appelle `POST /v1/chat` avec son jeton de service.
4. FastAPI applique le rate limit avant le cache.
5. La cle de cache inclut hash de question, societe, departement, scopes, provider, modele, seuil et version documentaire.
6. Qdrant limite la recherche a la societe et aux visibilites autorisees.
7. FastAPI post-filtre les payloads, applique le seuil et refuse sans source.
8. Le provider genere une reponse contrainte par les chunks. Le mode `extractive` renvoie des extraits.
9. La reponse contient sources, confiance, latence, cache et besoin d'escalade.
10. Odoo recalcule l'autorisation de chaque document. Une divergence provoque un refus complet.
11. Odoo conserve messages et metriques dans PostgreSQL et affiche les citations.

## Modele d'autorisation

| Visibilite | Employe | Meme departement | Manager | RH |
|---|---:|---:|---:|---:|
| `employee` | oui | oui | oui | oui |
| `department` | non | oui | oui si meme departement | oui dans le contexte demande |
| `manager` | non | non | oui, global ou meme departement | oui |
| `hr` | non | non | non | oui |

La societe doit toujours correspondre. Les record rules isolent conversations et taches. Un manager lit les checklists de son equipe mais ne modifie pas leurs etats. Les employes n'ont aucun ACL sur les documents.

## Redis

- `onboarding:index:queue` : queue bloquante du worker.
- `onboarding:index:job:*` : metadonnees de job avec TTL.
- `onboarding:index:lock:*` : verrou `SET NX EX` libere par comparaison de proprietaire.
- `onboarding:indexed:*` : deduplication d'une version indexee.
- `onboarding:documents:version:*` : invalidation des caches par societe.
- `onboarding:cache:*` : reponse contextualisee avec TTL.
- `onboarding:session:*` : session minimale par utilisateur et conversation ; aucune question en clair.
- `onboarding:rate:*` : compteur par minute, societe et utilisateur.

Redis n'est pas une base principale. Sa perte supprime caches/sessions et peut imposer de relancer les documents `pending`, mais ne supprime aucune conversation Odoo.

## Providers

La configuration Docker par defaut utilise `LLM_PROVIDER=ollama` avec `qwen2.5:0.5b` pour une vraie generation locale, conversationnelle, adaptee au CPU et sans cle externe. La recherche conserve les embeddings locaux `hashing-128` et son garde lexical ; le modele ne voit ensuite que les chunks autorises recuperes par cette recherche.

Avec un modele d'embedding Ollama configure a la place de `hashing-128`, le service utilise `/api/embed`; la generation utilise `/api/chat`. Le provider `openai` compatible utilise `/v1/embeddings` et `/v1/chat/completions`. URLs, modeles et cles sont injectes par environnement. Les cles ne sont pas journalisees. Le mode `extractive` reste disponible pour les tests et le diagnostic.

Le prompt exige des citations `[n]`. FastAPI refuse avant generation lorsque le retrieval est insuffisant et ajoute une reference si le provider omet toute citation.

## Escalade RH

Un refus affiche `Transmettre a RH`. L'action cree une `mail.activity` sur la fiche employe et conserve uniquement question et identifiant de conversation. Une meme reponse ne cree qu'une activite.

## Evaluation et tests

Le dataset `services/onboarding_ai/evaluation/dataset.json` contient 30 questions couvrant employe, departement, manager, RH, multi-societe et inconnu.

`python -m evaluation.run_evaluation` mesure citations correctes, refus corrects, exactitude, latence moyenne/P95, cache et escalade.

Baseline deterministe du 28 aout 2026 : 95,65 % de citations correctes, 100 % de refus corrects et 96,67 % d'exactitude globale. C'est un test de regression local, pas une certification sur le corpus d'une organisation.

## Kubernetes

`deploy/k8s` fournit ConfigMap, template Secret vide, API, worker, Services ClusterIP, Redis, Qdrant, PVC, probes et ressources. Le tag d'image est volontairement invalide avant choix d'une release.

Avant production : gestionnaire de secrets, stockage RWX, sauvegarde/replication, NetworkPolicies, TLS, observabilite, tests de charge, politique de retention et validation sur le cluster cible. Les manifests ont uniquement passe `kubectl kustomize` et ne sont pas declares production-ready.

## Confidentialite et limites

- Les questions completes restent dans Odoo ; Redis ne conserve qu'un hash de session.
- Les chunks Qdrant sont internes et les volumes doivent rester prives.
- Un provider externe recoit question et chunks selectionnes ; son usage doit etre approuve.
- Aucun OCR n'est fourni. Un PDF scanne vide produit une erreur d'indexation.
- Le score est un indicateur de retrieval, pas une probabilite de verite.
- Une source peut etre obsolete si le document RH est obsolete ; la gouvernance documentaire reste indispensable.
