import base64
import hashlib

from odoo import api, fields, models
from odoo.tools import file_open


class PortailRHCompanyDemo(models.AbstractModel):
    _name = "portail_rh.company.demo"
    _description = "Jeu de donnees entreprise Portail RH"

    EMPLOYEES = (
        ("1001", "Said Hammane", "said.hammane@bravico.ma", "hr@local.test", "Direction", "Gerant", "hr", "201", "+212 6 61 20 10 01"),
        ("1002", "Salma Alaoui", "salma.alaoui@bravico.ma", "employee@local.test", "Produit & IA", "Product Analyst", "employee", "202", "+212 6 61 20 10 02"),
        ("1003", "Youssef Benali", "youssef.benali@bravico.ma", "manager@local.test", "Engineering", "Tech Lead", "manager", "203", "+212 6 61 20 10 03"),
        ("1004", "Mariam Zahra", "mariam.zahra@bravico.ma", "mariam.zahra@bravico.ma", "Finance & Administration", "People Operations Specialist", "employee", "204", "+212 6 61 20 10 04"),
        ("1005", "Khalid Rachidi", "khalid.rachidi@bravico.ma", "khalid.rachidi@bravico.ma", "Finance & Administration", "Responsable Finance & Administration", "manager", "205", "+212 6 61 20 10 05"),
        ("1006", "Hicham Kettani", "hicham.kettani@bravico.ma", "hicham.kettani@bravico.ma", "Engineering", "DevOps Engineer", "employee", "206", "+212 6 61 20 10 06"),
        ("1007", "Leila Fassi", "leila.fassi@bravico.ma", "leila.fassi@bravico.ma", "Customer Success", "Customer Success Manager", "manager", "207", "+212 6 61 20 10 07"),
        ("1008", "Souad Idrissi", "souad.idrissi@bravico.ma", "souad.idrissi@bravico.ma", "Finance & Administration", "Comptable", "employee", "208", "+212 6 61 20 10 08"),
        ("1009", "Reda Soussi", "reda.soussi@bravico.ma", "reda.soussi@bravico.ma", "Commercial & Marketing", "Sales Development Representative", "employee", "209", "+212 6 61 20 10 09"),
        (False, "Nadia Amrani", "nadia.amrani@bravico.ma", "nadia.amrani@bravico.ma", "Commercial & Marketing", "Head of Sales & Marketing", "manager", "210", "+212 6 61 20 10 10"),
        (False, "Omar Tazi", "omar.tazi@bravico.ma", "omar.tazi@bravico.ma", "Customer Success", "Customer Success Specialist", "employee", "211", "+212 6 61 20 10 11"),
        (False, "Imane Berrada", "imane.berrada@bravico.ma", "imane.berrada@bravico.ma", "Produit & IA", "Product & AI Lead", "manager", "212", "+212 6 61 20 10 12"),
        (False, "Mehdi Alaoui", "mehdi.alaoui@bravico.ma", "mehdi.alaoui@bravico.ma", "Engineering", "Software Engineer", "employee", "213", "+212 6 61 20 10 13"),
    )

    DOCUMENTS = (
        (
            "Guide de l'employe Bravico",
            "guide-employe-bravico.txt",
            "welcome",
            "employee",
            False,
            """BRAVICO SARL AU - GUIDE DE L'EMPLOYE / EMPLOYEE HANDBOOK

Bienvenue chez Bravico, editeur marocain de logiciels SaaS simples et fiables pour les PME, base a Casablanca. Notre signature est: La simplicite qui paie.

HORAIRES / WORKING HOURS
La semaine de travail est du lundi au vendredi. Les horaires habituels sont 09:00-18:00 avec une pause dejeuner de 13:00 a 14:00. Une tolerance de dix minutes est admise. Tout retard doit etre signale au manager.

TELETRAVAIL / REMOTE WORK
Deux jours de teletravail par semaine sont possibles apres la periode d'essai, avec accord du manager. Les jours doivent etre declares avant jeudi pour la semaine suivante. Une connexion VPN est obligatoire hors des bureaux.

CONGES / LEAVE
Chaque collaborateur dispose de 18 jours ouvrables de conge annuel. Une demande de moins de trois jours doit etre envoyee 7 jours a l'avance; au-dela, 15 jours a l'avance. Les absences maladie doivent etre signalees le jour meme et justifiees sous 48 heures.

PAIE / PAYROLL
Le salaire est verse le dernier jour ouvrable du mois. Les bulletins sont disponibles aupres de l'administration. Toute question de paie doit etre envoyee a contact@bravico.ma.

PERIODE D'ESSAI / PROBATION
La periode d'essai standard est de trois mois, renouvelable une fois selon le contrat. Un point est organise avec le manager apres 30, 60 et 90 jours.

CONTACTS
Administration: contact@bravico.ma - poste 201. Support: support@bravico.ma - poste 207. Telephone principal: +212 6 39 26 99 45.
""",
        ),
        (
            "Identite et contacts officiels Bravico",
            "identite-contacts-bravico.txt",
            "welcome",
            "employee",
            False,
            """FICHE ENTREPRISE BRAVICO

Raison sociale: Bravico SARL AU.
Activite: conception et exploitation de logiciels simples et fiables pour les PME marocaines.
Localisation: Casablanca, Maroc.
Site web: https://bravico.ma
Contact officiel Bravico: email contact@bravico.ma et telephone/WhatsApp +212 6 39 26 99 45.
Registre de commerce: RC 689915.
Identifiant commun de l'entreprise: ICE 003790052000007.
Taxe professionnelle: 32302012.

Produits principaux: Bravico Pilotage, assistant de pilotage operationnel base sur les donnees et documents de l'entreprise, et EFacture Express, solution de facturation electronique pour les PME marocaines.
""",
        ),
        (
            "Produits et services Bravico",
            "produits-services-bravico.txt",
            "other",
            "employee",
            False,
            """PRODUITS ET SERVICES BRAVICO

Bravico Pilotage aide les managers a obtenir des reponses operationnelles sur la tresorerie, les relances, le stock, les clients, les reunions et les documents de l'entreprise.

EFacture Express simplifie la creation, l'import, le stockage et la preparation des factures electroniques. Le produit est concu pour accompagner les PME marocaines dans leur conformite a la facturation electronique.

Bravico propose egalement des logiciels sur mesure, de l'automatisation documentaire, du reporting operationnel et un accompagnement a la structuration des donnees d'entreprise.

Pour une demonstration ou une question commerciale: contact@bravico.ma ou +212 6 39 26 99 45.
""",
        ),
        (
            "Services RH et demandes internes",
            "services-rh.txt",
            "policy",
            "employee",
            False,
            """SERVICES RH - MODE D'EMPLOI

DEPLACEMENTS / BUSINESS TRAVEL
Une mission se cree depuis Mes deplacements > Nouvelle demande. Indiquez destination, dates, motif et cout estime. Le manager valide avant toute reservation. Les justificatifs de frais sont remis dans les cinq jours ouvrables suivant le retour.

FOURNITURES / EQUIPMENT
Une demande de PC, ecran, casque, telephone ou fournitures se cree depuis Mes fournitures. Le manager valide le besoin puis RH ou IT organise la remise. Le materiel reste la propriete de l'entreprise.

ATTESTATIONS / CERTIFICATES
Les attestations de travail ou de salaire se demandent depuis Mes attestations. Le delai habituel est de deux jours ouvrables. Une attestation approuvee peut etre telechargee en PDF depuis le portail.

ESCALADE
Si l'assistant ne trouve pas une reponse verifiee, utilisez Transmettre a RH. Une activite est creee pour l'equipe RH sans envoyer de donnees sensibles inutiles.
""",
        ),
        (
            "Avantages, restauration et formation",
            "avantages-formation.txt",
            "benefits",
            "employee",
            False,
            """AVANTAGES COLLABORATEURS / EMPLOYEE BENEFITS

L'entreprise prend en charge une assurance maladie complementaire apres la periode d'essai. La couverture famille peut etre ajoutee avec une participation mensuelle.

Une indemnite repas de 40 MAD est accordee par jour travaille sur site. Le transport tardif est rembourse avec accord du manager lorsque le depart intervient apres 21:00.

Chaque collaborateur dispose d'un budget annuel de formation de 6 000 MAD. Les certifications liees au poste sont validees par le manager et RH. Une demi-journee par mois peut etre consacree a l'apprentissage.

Le programme de recommandation verse une prime de 3 000 MAD apres validation de la periode d'essai du candidat recrute.
""",
        ),
        (
            "Guide informatique et securite",
            "guide-it-securite.txt",
            "it",
            "employee",
            False,
            """GUIDE IT ET SECURITE / IT HELP

Le compte professionnel est active le premier jour. Le mot de passe doit contenir au moins 14 caracteres et l'authentification multifacteur est obligatoire. Ne partagez jamais un mot de passe ou un code MFA.

Pour le Wi-Fi du bureau, utilisez le reseau ATLAS-STAFF avec vos identifiants professionnels. Le reseau ATLAS-GUEST est reserve aux visiteurs.

Pour travailler a distance, ouvrez Bravico VPN puis connectez-vous avec le MFA. En cas de probleme de VPN, redemarrez le client et contactez support@bravico.ma ou le poste 207.

Tout email suspect, demande urgente de paiement ou lien de connexion inhabituel doit etre signale avec le bouton Phishing dans Outlook. N'ouvrez pas la piece jointe.

Un ordinateur perdu ou vole doit etre signale immediatement au support IT et au manager afin de verrouiller l'appareil.
""",
        ),
        (
            "Procedures equipe Produit et IA",
            "procedures-produit-ia.txt",
            "it",
            "department",
            "Produit & IA",
            """PROCEDURES DE L'EQUIPE PRODUIT ET IA

Le daily meeting a lieu a 09:30. Les changements de production exigent une pull request approuvee, des tests verts et une fenetre de deploiement annoncee. Les incidents P1 sont signales dans le canal incident et au responsable infrastructure.

Les astreintes sont planifiees un mois a l'avance. Le temps d'intervention hors horaires est recupere conformement au planning valide par le manager.
""",
        ),
        (
            "Guide confidentiel des managers",
            "guide-managers.txt",
            "policy",
            "manager",
            False,
            """GUIDE MANAGER

Le manager organise les points 30/60/90 jours, valide les demandes de mission et de fournitures, et suit la checklist de son equipe sans modifier les taches a la place du collaborateur.

Les objectifs trimestriels sont definis avec des resultats mesurables. Les sujets disciplinaires, medicaux ou salariaux individuels doivent etre transmis a RH et ne doivent jamais etre discutes dans un canal public.
""",
        ),
    )

    @api.model
    def seed(self, password):
        if not password or len(password) < 12:
            raise ValueError("A local demo password of at least 12 characters is required")
        env = self.sudo().env
        company = env.company
        country = env.ref("base.ma", raise_if_not_found=False)
        with file_open("portail_rh/static/src/img/bravico-horizontal.png", "rb") as logo_file:
            company_logo = base64.b64encode(logo_file.read())
        with file_open("portail_rh/static/src/img/bravico-square.png", "rb") as favicon_file:
            website_favicon = base64.b64encode(favicon_file.read())
        company_values = {
            "name": "Bravico SARL AU",
            "email": "contact@bravico.ma",
            "phone": "+212 6 39 26 99 45",
            "website": "https://bravico.ma",
            "street": False,
            "city": "Casablanca",
            "zip": False,
            "country_id": country.id if country else False,
            "logo": company_logo,
        }
        if "company_registry" in company._fields:
            company_values["company_registry"] = (
                "RC 689915 | ICE 003790052000007 | TP 32302012"
            )
        company.write(company_values)
        websites = env["website"].search([("company_id", "=", company.id)])
        for website in websites:
            website_values = {
                "name": "Bravico",
                "logo": company_logo,
                "favicon": website_favicon,
            }
            website.write(website_values)
        header_contact_view = env.ref(
            "website.header_text_element", raise_if_not_found=False
        )
        if header_contact_view:
            header_arch = header_contact_view.arch_db
            header_arch = header_arch.replace(
                "+1 555-555-5556", company.phone
            ).replace(
                "info@yourcompany.example.com", company.email
            )
            if header_arch != header_contact_view.arch_db:
                header_contact_view.write({"arch_db": header_arch})
        departments = {}
        for name in {item[4] for item in self.EMPLOYEES}:
            department = env["hr.department"].search(
                [("name", "=", name), ("company_id", "in", [False, company.id])], limit=1
            )
            if not department:
                department = env["hr.department"].create({"name": name, "company_id": company.id})
            departments[name] = department

        groups = {
            "employee": env.ref("portail_rh.group_portail_rh_employee"),
            "manager": env.ref("portail_rh.group_portail_rh_manager"),
            "hr": env.ref("portail_rh.group_portail_rh_hr"),
        }
        portal_action = env.ref("portail_rh.action_employee_portal_home")
        employees = {}
        department_managers = {}
        for (
            device_id,
            name,
            work_email,
            login,
            department_name,
            job_name,
            role,
            extension,
            mobile_phone,
        ) in self.EMPLOYEES:
            job = env["hr.job"].search(
                [("name", "=", job_name), ("company_id", "=", company.id)], limit=1
            )
            if not job:
                job = env["hr.job"].create({"name": job_name, "company_id": company.id})
            user = env["res.users"].search(
                ["|", ("login", "=", login), ("name", "=", name)], limit=1
            )
            user_values = {
                "name": name,
                "login": login,
                "email": work_email,
                "password": password,
                "active": True,
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "groups_id": [(6, 0, [groups[role].id])],
                "action_id": portal_action.id if role == "employee" else False,
            }
            if user:
                user.write(user_values)
            else:
                user = env["res.users"].create(user_values)
            employee = env["hr.employee"].search(
                [
                    "|",
                    "|",
                    ("user_id", "=", user.id),
                    ("work_email", "=ilike", work_email),
                    ("name", "=", name),
                ],
                limit=1,
            )
            employee_values = {
                "name": name,
                "user_id": user.id,
                "work_email": work_email,
                "department_id": departments[department_name].id,
                "job_id": job.id,
                "company_id": company.id,
                "work_phone": "%s poste %s" % (company.phone, extension),
                "mobile_phone": mobile_phone,
                "zkteco_user_id": device_id or False,
            }
            if employee:
                employee.write(employee_values)
            else:
                employee = env["hr.employee"].create(employee_values)
            employees[login] = employee
            if role in ("manager", "hr") and department_name not in department_managers:
                department_managers[department_name] = employee

        for department_name, department in departments.items():
            manager = department_managers.get(department_name)
            if manager:
                department.manager_id = manager.id
        for employee in employees.values():
            manager = department_managers.get(employee.department_id.name)
            if manager and employee != manager:
                employee.parent_id = manager.id

        documents_to_index = env["hr.onboarding.document"].browse()
        documents = {}
        legacy_titles = {
            "Guide de l'employe Bravico": "Guide de l'employe Atlas Digital",
            "Procedures equipe Produit et IA": "Procedures equipe Informatique",
        }
        for title, filename, category, visibility, department_name, content in self.DOCUMENTS:
            content_bytes = content.encode("utf-8")
            checksum = hashlib.sha256(content_bytes).hexdigest()
            document = env["hr.onboarding.document"].search(
                [("name", "=", title), ("company_id", "=", company.id)], limit=1
            )
            if not document and legacy_titles.get(title):
                document = env["hr.onboarding.document"].search(
                    [
                        ("name", "=", legacy_titles[title]),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
            values = {
                "name": title,
                "file_name": filename,
                "file_data": base64.b64encode(content_bytes),
                "category": category,
                "language": "fr",
                "company_id": company.id,
                "department_id": departments[department_name].id if department_name else False,
                "visibility": visibility,
                "active": True,
            }
            if not document:
                document = env["hr.onboarding.document"].create(values)
            elif document.checksum != checksum:
                document.write(values)
            elif document.indexing_state != "indexed":
                documents_to_index |= document
            documents[title] = document
        if documents_to_index:
            documents_to_index._schedule_indexing()

        plans = (
            ("Parcours commun - 30 premiers jours", False, (
                (10, "Decouvrir le guide de l'employe", "Lire les horaires, conges et contacts utiles."),
                (20, "Configurer le compte et le MFA", "Activer le compte professionnel et l'authentification multifacteur."),
                (30, "Rencontrer son manager", "Faire le point sur les objectifs des 30 premiers jours."),
                (40, "Terminer la sensibilisation securite", "Valider le module phishing et protection des donnees."),
                (50, "Donner un feedback d'integration", "Partager les points clairs et les besoins restants avec RH."),
            )),
            ("Parcours equipe Produit & IA", "Produit & IA", (
                (10, "Installer les outils de developpement", "Configurer Git, VPN, environnement local et acces projets."),
                (20, "Lire la procedure de mise en production", "Comprendre les revues, tests et fenetres de deploiement."),
                (30, "Participer au daily Produit", "Se presenter et partager son premier objectif d'equipe."),
            )),
        )
        for plan_name, department_name, lines in plans:
            plan = env["hr.onboarding.plan"].search([("name", "=", plan_name)], limit=1)
            if not plan and plan_name == "Parcours equipe Produit & IA":
                plan = env["hr.onboarding.plan"].search(
                    [("name", "=", "Parcours equipe Informatique")], limit=1
                )
            plan_values = {
                "name": plan_name,
                "department_id": departments[department_name].id if department_name else False,
                "active": True,
            }
            if plan:
                plan.write(plan_values)
            else:
                plan = env["hr.onboarding.plan"].create(plan_values)
            for sequence, line_name, description in lines:
                line = env["hr.onboarding.plan.line"].search(
                    [("plan_id", "=", plan.id), ("name", "=", line_name)], limit=1
                )
                if not line and line_name == "Participer au daily Produit":
                    line = env["hr.onboarding.plan.line"].search(
                        [
                            ("plan_id", "=", plan.id),
                            ("name", "=", "Participer au daily IT"),
                        ],
                        limit=1,
                    )
                line_values = {
                    "plan_id": plan.id,
                    "name": line_name,
                    "description": description,
                    "sequence": sequence,
                    "required": True,
                }
                line.write(line_values) if line else env["hr.onboarding.plan.line"].create(line_values)

        demo_employees = env["hr.employee"].browse(
            [employee.id for employee in employees.values()]
        )
        demo_tasks = env["hr.onboarding.employee.task"].search(
            [("employee_id", "in", demo_employees.ids)]
        )
        stale_tasks = demo_tasks.filtered(
            lambda task: task.plan_line_id.plan_id.department_id
            and task.plan_line_id.plan_id.department_id != task.employee_id.department_id
        )
        stale_tasks.unlink()

        for employee in demo_employees:
            tasks = env["hr.onboarding.employee.task"].ensure_for_employee(employee)
            if employee.user_id.login == "employee@local.test":
                tasks[:2].write({"state": "done"})
                tasks[2:3].write({"state": "in_progress"})

        sample_employee = employees["employee@local.test"]
        self._seed_requests(env, sample_employee, employees)
        conversation = env["hr.onboarding.conversation"].search(
            [("user_id", "=", sample_employee.user_id.id), ("active", "=", True)], limit=1
        )
        welcome_content = (
            "Bonjour Salma ! Je suis Bravi, l'assistant RH de Bravico. Je peux "
            "vous aider sur l'entreprise, les produits, les contacts, les horaires, "
            "le teletravail, les avantages, le support et les demandes RH. Mes "
            "reponses utilisent uniquement les documents autorises."
        )
        if not conversation:
            conversation = env["hr.onboarding.conversation"].create(
                {"user_id": sample_employee.user_id.id, "employee_id": sample_employee.id}
            )
        welcome_message = env["hr.onboarding.message"].search(
            [
                ("conversation_id", "=", conversation.id),
                ("role", "=", "assistant"),
                ("content", "ilike", "Bonjour Salma"),
            ],
            order="id asc",
            limit=1,
        )
        welcome_values = {
            "conversation_id": conversation.id,
            "role": "assistant",
            "content": welcome_content,
            "source_document_ids": [
                (6, 0, [documents["Guide de l'employe Bravico"].id])
            ],
            "source_payload": "[]",
        }
        if welcome_message:
            welcome_message.write(welcome_values)
        else:
            env["hr.onboarding.message"].create(welcome_values)

        log_model = env["hr.attendance.device.log"]
        mapped = log_model._map_unmatched_logs()
        processed = log_model._process_mapped_logs()
        return {
            "users": len(employees),
            "employees": len(employees),
            "documents": len(documents),
            "plans": len(plans),
            "mapped_logs": mapped,
            **processed,
        }

    @api.model
    def _seed_requests(self, env, sample_employee, employees):
        travel_values = (
            ("Mission client Rabat", sample_employee, "Rabat", "2026-09-08", "2026-09-10", 2400, "Atelier de cadrage client", "submitted"),
            ("Conference technologique Marrakech", sample_employee, "Marrakech", "2026-07-14", "2026-07-16", 3800, "Participation conference et networking", "done"),
            ("Audit financier Tanger", employees["manager@local.test"], "Tanger", "2026-09-21", "2026-09-23", 3200, "Revue trimestrielle", "approved"),
        )
        for name, employee, destination, date_from, date_to, cost, purpose, state in travel_values:
            if not env["hr.travel.request"].search_count([("name", "=", name)]):
                env["hr.travel.request"].create(
                    {"name": name, "employee_id": employee.id, "destination": destination, "date_from": date_from, "date_to": date_to, "estimated_cost": cost, "purpose": purpose, "state": state}
                )
        supply_values = (
            (sample_employee, "Ecran 27 pouces", 1, 2600, "Ameliorer le poste de developpement", "approved"),
            (sample_employee, "Casque antibruit", 1, 950, "Reunions clients et concentration", "submitted"),
            (employees["hr@local.test"], "PC portable RH", 1, 10500, "Renouvellement du poste recrutement", "done"),
        )
        for employee, item, quantity, cost, reason, state in supply_values:
            if not env["hr.supply.request"].search_count([("employee_id", "=", employee.id), ("item_name", "=", item)]):
                env["hr.supply.request"].create(
                    {"employee_id": employee.id, "item_name": item, "quantity": quantity, "estimated_cost": cost, "reason": reason, "state": state}
                )
        attestation_values = (
            (sample_employee, "work", "Dossier de location", "approved"),
            (sample_employee, "salary", "Dossier bancaire", "submitted"),
            (employees["khalid.rachidi@bravico.ma"], "work", "Demarche administrative", "done"),
        )
        for employee, kind, reason, state in attestation_values:
            if not env["hr.attestation.request"].search_count([("employee_id", "=", employee.id), ("reason", "=", reason)]):
                env["hr.attestation.request"].create(
                    {"employee_id": employee.id, "attestation_type": kind, "reason": reason, "request_date": fields.Date.context_today(self), "state": state}
                )
