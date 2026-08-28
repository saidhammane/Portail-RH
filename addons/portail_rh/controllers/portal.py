from collections import OrderedDict
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from markupsafe import escape
from werkzeug.exceptions import NotFound

from odoo import _, fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import UserError, ValidationError
from odoo.http import content_disposition, request


LOGGER = logging.getLogger(__name__)
ONBOARDING_REFUSAL = _("Information insuffisante dans les documents autorises.")


class PortailRHPortal(CustomerPortal):
    REQUEST_CONFIG = {
        "travel": {
            "model": "hr.travel.request",
            "url": "/my/travel_requests",
            "history": "my_travel_requests_history",
            "record_key": "travel_request",
            "records_key": "travel_requests",
            "list_template": "portail_rh.portal_my_travel_requests",
            "detail_template": "portail_rh.portal_travel_request_detail",
            "new_template": "portail_rh.portal_new_travel_request",
            "page_prefix": "travel_request",
        },
        "supply": {
            "model": "hr.supply.request",
            "url": "/my/supply_requests",
            "history": "my_supply_requests_history",
            "record_key": "supply_request",
            "records_key": "supply_requests",
            "list_template": "portail_rh.portal_my_supply_requests",
            "detail_template": "portail_rh.portal_supply_request_detail",
            "new_template": "portail_rh.portal_new_supply_request",
            "page_prefix": "supply_request",
        },
        "attestation": {
            "model": "hr.attestation.request",
            "url": "/my/attestation_requests",
            "history": "my_attestation_requests_history",
            "record_key": "attestation_request",
            "records_key": "attestation_requests",
            "list_template": "portail_rh.portal_my_attestation_requests",
            "detail_template": "portail_rh.portal_attestation_request_detail",
            "new_template": "portail_rh.portal_new_attestation_request",
            "page_prefix": "attestation_request",
        },
    }

    FORM_DEFAULTS = {
        "travel": {
            "destination": "",
            "date_from": "",
            "date_to": "",
            "purpose": "",
            "estimated_cost": "",
        },
        "supply": {
            "item_name": "",
            "description": "",
            "quantity": "1",
            "estimated_cost": "",
            "reason": "",
        },
        "attestation": {
            "attestation_type": "",
            "reason": "",
        },
    }

    def _request_domain(self):
        return [("employee_id.user_id", "=", request.env.user.id)]

    def _current_employee(self):
        employee = request.env["hr.employee"].search(
            [("user_id", "=", request.env.user.id)], limit=1
        )
        if not employee:
            raise NotFound()
        return employee

    def _request_record(self, request_type, request_id):
        config = self.REQUEST_CONFIG[request_type]
        record = request.env[config["model"]].search(
            self._request_domain() + [("id", "=", request_id)], limit=1
        )
        if not record:
            raise NotFound()
        return record

    def _selection_values(self, model_name, field_name):
        return request.env[model_name].fields_get([field_name])[field_name]["selection"]

    def _state_labels(self, model_name):
        return dict(self._selection_values(model_name, "state"))

    def _searchbar_filters(self):
        return OrderedDict(
            (state, {"label": label, "domain": [] if state == "all" else [("state", "=", state)]})
            for state, label in (
                ("all", _("Toutes")),
                ("draft", _("Brouillon")),
                ("submitted", _("Soumises")),
                ("approved", _("Approuvees")),
                ("rejected", _("Refusees")),
                ("done", _("Terminees")),
            )
        )

    def _searchbar_sortings(self, request_type):
        common = {
            "name": {"label": _("Reference"), "order": "name asc, id desc"},
            "state": {"label": _("Etat"), "order": "state asc, create_date desc, id desc"},
        }
        if request_type == "travel":
            return OrderedDict(
                [
                    ("date", {"label": _("Date de debut"), "order": "date_from desc, id desc"}),
                    ("name", common["name"]),
                    (
                        "destination",
                        {"label": _("Destination"), "order": "destination asc, date_from desc"},
                    ),
                    ("state", common["state"]),
                ]
            )
        if request_type == "supply":
            return OrderedDict(
                [
                    ("date", {"label": _("Date de creation"), "order": "create_date desc, id desc"}),
                    ("name", common["name"]),
                    ("item", {"label": _("Article"), "order": "item_name asc, id desc"}),
                    ("state", common["state"]),
                ]
            )
        return OrderedDict(
            [
                ("date", {"label": _("Date de demande"), "order": "request_date desc, id desc"}),
                ("name", common["name"]),
                ("type", {"label": _("Type"), "order": "attestation_type asc, id desc"}),
                ("state", common["state"]),
            ]
        )

    def _feedback_message(self, request_type, code):
        return {
            ("travel", "created"): _("Votre demande de deplacement a ete creee en brouillon."),
            ("travel", "submitted"): _("Votre demande de deplacement a ete soumise."),
            ("supply", "created"): _("Votre demande de fournitures a ete creee en brouillon."),
            ("supply", "submitted"): _("Votre demande de fournitures a ete soumise."),
            ("attestation", "created"): _("Votre demande d'attestation a ete creee en brouillon."),
            ("attestation", "submitted"): _("Votre demande d'attestation a ete soumise."),
        }.get((request_type, code))

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        for request_type, counter in (
            ("travel", "travel_request_count"),
            ("supply", "supply_request_count"),
            ("attestation", "attestation_request_count"),
        ):
            if counter not in counters:
                continue
            model = request.env[self.REQUEST_CONFIG[request_type]["model"]]
            values[counter] = (
                model.search_count(self._request_domain())
                if model.check_access_rights("read", raise_exception=False)
                else 0
            )
        if "onboarding_task_count" in counters:
            try:
                employee = self._current_employee()
                tasks = request.env["hr.onboarding.employee.task"].ensure_for_employee(
                    employee
                )
                values["onboarding_task_count"] = len(
                    tasks.filtered(lambda task: task.state != "done")
                )
            except NotFound:
                values["onboarding_task_count"] = 0
        return values

    def _onboarding_scopes(self):
        scopes = ["employee"]
        if request.env.user.has_group("portail_rh.group_portail_rh_manager"):
            scopes.append("manager")
        if request.env.user.has_group("portail_rh.group_portail_rh_hr"):
            scopes.append("hr")
        return scopes

    def _onboarding_conversation(self, employee):
        conversation = request.env["hr.onboarding.conversation"].search(
            [("user_id", "=", request.env.user.id), ("active", "=", True)],
            order="last_message_at desc, id desc",
            limit=1,
        )
        if not conversation:
            conversation = request.env["hr.onboarding.conversation"].create(
                {"employee_id": employee.id}
            )
        return conversation

    def _call_onboarding_ai(self, payload):
        service_url = os.getenv("ONBOARDING_AI_URL", "").rstrip("/")
        service_token = os.getenv("ONBOARDING_AI_SERVICE_TOKEN")
        if not service_url or not service_token:
            raise UserError(_("Le service d'assistance n'est pas configure."))
        http_request = Request(
            service_url + "/v1/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Service-Token": service_token,
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 429:
                raise UserError(_("Trop de questions ont ete envoyees. Reessayez plus tard."))
            LOGGER.warning("Onboarding chat request failed with HTTP %s", error.code)
            raise UserError(_("Le service d'assistance est temporairement indisponible."))
        except (URLError, TimeoutError, ValueError):
            LOGGER.warning("Onboarding chat request failed")
            raise UserError(_("Le service d'assistance est temporairement indisponible."))

    def _allowed_onboarding_documents(self, employee, scopes, source_ids):
        if not source_ids:
            return request.env["hr.onboarding.document"].sudo().browse()
        company = employee.company_id or request.env.company
        documents = request.env["hr.onboarding.document"].sudo().search(
            [
                ("id", "in", source_ids),
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("indexing_state", "=", "indexed"),
            ]
        )

        def is_allowed(document):
            if document.visibility == "employee":
                return True
            if document.visibility == "department":
                return bool(
                    employee.department_id
                    and document.department_id == employee.department_id
                )
            if document.visibility == "manager":
                if "hr" in scopes:
                    return True
                return bool(
                    "manager" in scopes
                    and (
                        not document.department_id
                        or document.department_id == employee.department_id
                    )
                )
            return document.visibility == "hr" and "hr" in scopes

        return documents.filtered(is_allowed)

    def _onboarding_values(self, employee, conversation, error=None, message=None):
        tasks = request.env["hr.onboarding.employee.task"].ensure_for_employee(employee)
        messages = conversation.message_ids.sudo()
        source_details = {}
        for chat_message in messages.filtered(lambda item: item.role == "assistant"):
            try:
                source_details[chat_message.id] = json.loads(
                    chat_message.source_payload or "[]"
                )
            except (TypeError, ValueError):
                source_details[chat_message.id] = []
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "page_name": "onboarding",
                "employee": employee,
                "conversation": conversation,
                "messages": messages,
                "message_sources": source_details,
                "onboarding_tasks": tasks,
                "completed_task_count": len(
                    tasks.filtered(lambda task: task.state == "done")
                ),
                "task_state_labels": dict(
                    request.env["hr.onboarding.employee.task"].fields_get(["state"])[
                        "state"
                    ]["selection"]
                ),
                "error_message": error,
                "success_message": {
                    "feedback": _("Merci pour votre retour."),
                    "escalated": _("Votre question a ete transmise a l'equipe RH."),
                }.get(message),
            }
        )
        return values

    def _list_values(self, request_type, page, sortby, filterby):
        config = self.REQUEST_CONFIG[request_type]
        model = request.env[config["model"]]
        sortings = self._searchbar_sortings(request_type)
        filters = self._searchbar_filters()
        sortby = sortby if sortby in sortings else "date"
        filterby = filterby if filterby in filters else "all"
        domain = self._request_domain() + filters[filterby]["domain"]
        pager = portal_pager(
            url=config["url"],
            total=model.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={"sortby": sortby, "filterby": filterby},
        )
        records = model.search(
            domain,
            order=sortings[sortby]["order"],
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session[config["history"]] = records.ids[:100]
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "default_url": config["url"],
                "filterby": filterby,
                "page_name": "%ss" % config["page_prefix"],
                "pager": pager,
                "portal_records": records,
                "portal_state_labels": self._state_labels(config["model"]),
                "request_type": request_type,
                "searchbar_filters": filters,
                "searchbar_sortings": sortings,
                "sortby": sortby,
                "success_message": None,
            }
        )
        values[config["records_key"]] = records
        if request_type == "attestation":
            values["attestation_type_labels"] = dict(
                self._selection_values(config["model"], "attestation_type")
            )
        return values

    def _detail_values(self, request_type, record, message=None, error=None):
        config = self.REQUEST_CONFIG[request_type]
        values = self._prepare_portal_layout_values()
        values.update(
            {
                config["record_key"]: record,
                "default_url": config["url"],
                "error_message": error,
                "page_name": "%s_detail" % config["page_prefix"],
                "portal_state_labels": self._state_labels(config["model"]),
                "request_type": request_type,
                "portal_record": record,
                "success_message": self._feedback_message(request_type, message),
            }
        )
        if request_type == "attestation":
            values["attestation_type_labels"] = dict(
                self._selection_values(config["model"], "attestation_type")
            )
        return self._get_page_view_values(
            record, None, values, config["history"], no_breadcrumbs=False
        )

    def _form_values(self, request_type, post=None, error=None):
        post = post or {}
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "error_message": error,
                "default_url": self.REQUEST_CONFIG[request_type]["url"],
                "form_values": {
                    field: post.get(field, default)
                    for field, default in self.FORM_DEFAULTS[request_type].items()
                },
                "page_name": "%s_new" % self.REQUEST_CONFIG[request_type]["page_prefix"],
                "request_type": request_type,
            }
        )
        if request_type == "attestation":
            values["attestation_types"] = self._selection_values(
                self.REQUEST_CONFIG[request_type]["model"], "attestation_type"
            )
        return values

    def _create_values(self, request_type, employee, values):
        if request_type == "travel":
            destination = values["destination"].strip()
            return {
                "name": _("Deplacement - %s") % destination if destination else _("Nouvelle demande"),
                "employee_id": employee.id,
                "destination": destination,
                "date_from": values["date_from"],
                "date_to": values["date_to"],
                "purpose": values["purpose"],
                "estimated_cost": float(values["estimated_cost"] or 0),
                "state": "draft",
            }
        if request_type == "supply":
            return {
                "employee_id": employee.id,
                "item_name": values["item_name"].strip(),
                "description": values["description"],
                "quantity": float(values["quantity"] or 1),
                "estimated_cost": float(values["estimated_cost"] or 0),
                "reason": values["reason"],
                "state": "draft",
            }
        return {
            "employee_id": employee.id,
            "attestation_type": values["attestation_type"],
            "reason": values["reason"],
            "state": "draft",
        }

    def _render_list(self, request_type, page, sortby, filterby, message=None):
        config = self.REQUEST_CONFIG[request_type]
        values = self._list_values(request_type, page, sortby, filterby)
        values["success_message"] = self._feedback_message(request_type, message)
        return request.render(config["list_template"], values)

    def _render_detail(self, request_type, request_id, message=None, error=None):
        config = self.REQUEST_CONFIG[request_type]
        record = self._request_record(request_type, request_id)
        return request.render(
            config["detail_template"], self._detail_values(request_type, record, message, error)
        )

    def _render_new(self, request_type, post=None, error=None):
        config = self.REQUEST_CONFIG[request_type]
        return request.render(config["new_template"], self._form_values(request_type, post, error))

    def _create(self, request_type, post):
        config = self.REQUEST_CONFIG[request_type]
        values = self._form_values(request_type, post)["form_values"]
        try:
            record = request.env[config["model"]].create(
                self._create_values(request_type, self._current_employee(), values)
            )
        except (UserError, ValidationError, ValueError) as exc:
            return self._render_new(request_type, post, str(exc))
        return request.redirect("%s/%s?message=created" % (config["url"], record.id))

    def _submit(self, request_type, request_id):
        config = self.REQUEST_CONFIG[request_type]
        record = self._request_record(request_type, request_id)
        try:
            record.action_submit()
        except (UserError, ValidationError) as exc:
            return request.render(
                config["detail_template"], self._detail_values(request_type, record, error=str(exc))
            )
        return request.redirect("%s/%s?message=submitted" % (config["url"], record.id))

    @http.route(
        ["/my/travel_requests", "/my/travel_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_travel_requests(self, page=1, sortby=None, filterby=None, **kw):
        return self._render_list("travel", page, sortby, filterby, kw.get("message"))

    @http.route("/my/travel_requests/new", type="http", auth="user", website=True)
    def portal_new_travel_request(self, **kw):
        return self._render_new("travel", kw, kw.get("error_message"))

    @http.route("/my/travel_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_travel_request(self, **post):
        return self._create("travel", post)

    @http.route("/my/travel_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_travel_request_detail(self, request_id, **kw):
        return self._render_detail("travel", request_id, kw.get("message"), kw.get("error_message"))

    @http.route(
        "/my/travel_requests/<int:request_id>/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_travel_request(self, request_id, **post):
        return self._submit("travel", request_id)

    @http.route(
        ["/my/supply_requests", "/my/supply_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_supply_requests(self, page=1, sortby=None, filterby=None, **kw):
        return self._render_list("supply", page, sortby, filterby, kw.get("message"))

    @http.route("/my/supply_requests/new", type="http", auth="user", website=True)
    def portal_new_supply_request(self, **kw):
        return self._render_new("supply", kw, kw.get("error_message"))

    @http.route("/my/supply_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_supply_request(self, **post):
        return self._create("supply", post)

    @http.route("/my/supply_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_supply_request_detail(self, request_id, **kw):
        return self._render_detail("supply", request_id, kw.get("message"), kw.get("error_message"))

    @http.route(
        "/my/supply_requests/<int:request_id>/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_supply_request(self, request_id, **post):
        return self._submit("supply", request_id)

    @http.route(
        ["/my/attestation_requests", "/my/attestation_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_attestation_requests(self, page=1, sortby=None, filterby=None, **kw):
        return self._render_list("attestation", page, sortby, filterby, kw.get("message"))

    @http.route("/my/attestation_requests/new", type="http", auth="user", website=True)
    def portal_new_attestation_request(self, **kw):
        return self._render_new("attestation", kw, kw.get("error_message"))

    @http.route(
        "/my/attestation_requests/create",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_create_attestation_request(self, **post):
        return self._create("attestation", post)

    @http.route("/my/attestation_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_attestation_request_detail(self, request_id, **kw):
        return self._render_detail(
            "attestation", request_id, kw.get("message"), kw.get("error_message")
        )

    @http.route(
        "/my/attestation_requests/<int:request_id>/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_attestation_request(self, request_id, **post):
        return self._submit("attestation", request_id)

    @http.route(
        "/my/attestation_requests/<int:request_id>/pdf",
        type="http",
        auth="user",
        website=True,
    )
    def portal_attestation_request_pdf(self, request_id, **kw):
        record = self._request_record("attestation", request_id)
        if record.state not in ("approved", "done"):
            raise NotFound()
        pdf, _content_type = request.env.ref(
            "portail_rh.action_report_hr_attestation"
        )._render_qweb_pdf("portail_rh.report_attestation_document", res_ids=record.ids)
        filename = "Attestation_%s.pdf" % record.name.replace("/", "_")
        return request.make_response(
            pdf,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Length", len(pdf)),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )

    @http.route("/my/onboarding", type="http", auth="user", website=True)
    def portal_my_onboarding(self, **kw):
        employee = self._current_employee()
        conversation = self._onboarding_conversation(employee)
        return request.render(
            "portail_rh.portal_my_onboarding",
            self._onboarding_values(
                employee,
                conversation,
                error=kw.get("error_message"),
                message=kw.get("message"),
            ),
        )

    @http.route(
        "/my/onboarding/ask",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_onboarding_ask(self, **post):
        employee = self._current_employee()
        conversation = self._onboarding_conversation(employee)
        question = (post.get("question") or "").strip()
        if len(question) < 2 or len(question) > 2000:
            return request.render(
                "portail_rh.portal_my_onboarding",
                self._onboarding_values(
                    employee,
                    conversation,
                    error=_("La question doit contenir entre 2 et 2000 caracteres."),
                ),
            )
        Message = request.env["hr.onboarding.message"].sudo()
        Message.create(
            {
                "conversation_id": conversation.id,
                "role": "user",
                "content": question,
            }
        )
        scopes = self._onboarding_scopes()
        try:
            ai_response = self._call_onboarding_ai(
                {
                    "user_id": request.env.user.id,
                    "employee_id": employee.id,
                    "company_id": (employee.company_id or request.env.company).id,
                    "department_id": employee.department_id.id or None,
                    "group_scopes": scopes,
                    "question": question,
                    "conversation_id": conversation.id,
                }
            )
        except UserError as error:
            ai_response = {
                "answer": str(error),
                "sources": [],
                "confidence": 0.0,
                "latency_ms": 0,
                "cache_hit": False,
                "needs_escalation": True,
            }

        response_sources = ai_response.get("sources") or []
        source_ids = []
        for source in response_sources:
            try:
                source_ids.append(int(source["document_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        allowed_documents = self._allowed_onboarding_documents(
            employee, scopes, source_ids
        )
        if not source_ids or set(source_ids) != set(allowed_documents.ids):
            ai_response.update(
                {
                    "answer": str(ONBOARDING_REFUSAL),
                    "sources": [],
                    "confidence": 0.0,
                    "needs_escalation": True,
                }
            )
            allowed_documents = request.env["hr.onboarding.document"].sudo().browse()
        canonical_sources = []
        document_by_id = {document.id: document for document in allowed_documents}
        for source in ai_response.get("sources") or []:
            document = document_by_id.get(int(source["document_id"]))
            if document:
                canonical_sources.append(
                    {
                        "document_id": document.id,
                        "title": document.name,
                        "section": str(source.get("section") or "Section")[:255],
                        "score": max(0.0, min(1.0, float(source.get("score") or 0.0))),
                    }
                )
        assistant_message = Message.create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": str(ai_response.get("answer") or ONBOARDING_REFUSAL),
                "source_document_ids": [(6, 0, allowed_documents.ids)],
                "source_payload": json.dumps(canonical_sources),
                "confidence_score": max(
                    0.0, min(1.0, float(ai_response.get("confidence") or 0.0))
                ),
                "latency_ms": max(0, int(ai_response.get("latency_ms") or 0)),
                "cache_hit": bool(ai_response.get("cache_hit")),
                "needs_escalation": bool(ai_response.get("needs_escalation")),
            }
        )
        conversation.sudo().write({"last_message_at": fields.Datetime.now()})
        request.session["onboarding_last_message_id"] = assistant_message.id
        return request.redirect("/my/onboarding")

    @http.route(
        "/my/onboarding/checklist",
        type="http",
        auth="user",
        website=True,
    )
    def portal_onboarding_checklist(self, **kw):
        employee = self._current_employee()
        conversation = self._onboarding_conversation(employee)
        values = self._onboarding_values(employee, conversation, message=kw.get("message"))
        values["page_name"] = "onboarding_checklist"
        return request.render("portail_rh.portal_onboarding_checklist", values)

    @http.route(
        "/my/onboarding/checklist/<int:task_id>/state",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_onboarding_task_state(self, task_id, **post):
        employee = self._current_employee()
        task = request.env["hr.onboarding.employee.task"].search(
            [("id", "=", task_id), ("employee_id", "=", employee.id)], limit=1
        )
        if not task:
            raise NotFound()
        state = post.get("state")
        if state not in {"todo", "in_progress", "done"}:
            raise NotFound()
        task.write({"state": state})
        return request.redirect("/my/onboarding/checklist")

    @http.route(
        "/my/onboarding/feedback",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_onboarding_feedback(self, **post):
        feedback = post.get("feedback")
        if feedback not in {"helpful", "not_helpful"}:
            raise NotFound()
        message = request.env["hr.onboarding.message"].search(
            [
                ("id", "=", int(post.get("message_id") or 0)),
                ("role", "=", "assistant"),
                ("conversation_id.user_id", "=", request.env.user.id),
            ],
            limit=1,
        )
        if not message:
            raise NotFound()
        message.sudo().write({"feedback": feedback})
        return request.redirect("/my/onboarding?message=feedback")

    @http.route(
        "/my/onboarding/escalate",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_onboarding_escalate(self, **post):
        message = request.env["hr.onboarding.message"].search(
            [
                ("id", "=", int(post.get("message_id") or 0)),
                ("role", "=", "assistant"),
                ("needs_escalation", "=", True),
                ("conversation_id.user_id", "=", request.env.user.id),
            ],
            limit=1,
        )
        if not message:
            raise NotFound()
        if not message.escalation_activity_id:
            question_message = request.env["hr.onboarding.message"].sudo().search(
                [
                    ("conversation_id", "=", message.conversation_id.id),
                    ("role", "=", "user"),
                    ("id", "<", message.id),
                ],
                order="id desc",
                limit=1,
            )
            hr_group = request.env.ref("portail_rh.group_portail_rh_hr")
            hr_user = hr_group.users.filtered("active")[:1]
            todo_type = request.env.ref("mail.mail_activity_data_todo")
            if not hr_user or not question_message:
                raise NotFound()
            employee = message.conversation_id.employee_id
            activity = request.env["mail.activity"].sudo().create(
                {
                    "res_model_id": request.env["ir.model"]._get_id("hr.employee"),
                    "res_id": employee.id,
                    "user_id": hr_user.id,
                    "activity_type_id": todo_type.id,
                    "summary": _("Question d'integration a traiter"),
                    "note": "<p><strong>Conversation #%s</strong></p><p>%s</p>"
                    % (message.conversation_id.id, escape(question_message.content)),
                }
            )
            message.sudo().write(
                {
                    "escalated_at": fields.Datetime.now(),
                    "escalation_activity_id": activity.id,
                }
            )
        return request.redirect("/my/onboarding?message=escalated")
