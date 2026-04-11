from collections import OrderedDict

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class PortailRHPortal(CustomerPortal):
    def _get_portal_feedback_message(self, namespace, code):
        messages = {
            ("travel", "created"): _("Votre demande de deplacement a ete creee en brouillon."),
            ("travel", "submitted"): _("Votre demande de deplacement a ete soumise."),
            ("supply", "created"): _("Votre demande de fournitures a ete creee en brouillon."),
            ("supply", "submitted"): _("Votre demande de fournitures a ete soumise."),
        }
        return messages.get((namespace, code))

    def _get_current_employee(self):
        employee = request.env["hr.employee"].search([("user_id", "=", request.env.user.id)], limit=1)
        if not employee:
            raise NotFound()
        return employee

    def _get_request_state_labels(self, model_name):
        return dict(request.env[model_name].fields_get(["state"])["state"]["selection"])

    def _get_request_filters(self):
        return OrderedDict(
            [
                ("all", {"label": _("Toutes"), "domain": []}),
                ("draft", {"label": _("Brouillon"), "domain": [("state", "=", "draft")]}),
                ("submitted", {"label": _("Soumises"), "domain": [("state", "=", "submitted")]}),
                ("approved", {"label": _("Approuvees"), "domain": [("state", "=", "approved")]}),
                ("rejected", {"label": _("Refusees"), "domain": [("state", "=", "rejected")]}),
                ("done", {"label": _("Terminees"), "domain": [("state", "=", "done")]}),
            ]
        )

    def _get_request_portal_config(self, request_type):
        configs = {
            "travel": {
                "namespace": "travel",
                "model": "hr.travel.request",
                "list_route": "/my/travel_requests",
                "new_route": "/my/travel_requests/new",
                "submit_route": "/my/travel_requests/%s/submit",
                "history_key": "my_travel_requests_history",
                "record_key": "travel_request",
                "records_key": "travel_requests",
                "page_names": {
                    "list": "travel_requests",
                    "detail": "travel_request_detail",
                    "new": "travel_request_new",
                },
                "templates": {
                    "list": "portail_rh.portal_my_travel_requests",
                    "detail": "portail_rh.portal_travel_request_detail",
                    "new": "portail_rh.portal_new_travel_request",
                },
                "labels": {
                    "home_title": _("Mes deplacements"),
                    "list_title": _("Mes deplacements"),
                    "new_title": _("Nouvelle demande de deplacement"),
                    "empty": _("Aucune demande de deplacement pour le moment."),
                },
                "sortings": OrderedDict(
                    [
                        (
                            "date",
                            {
                                "label": _("Date de debut"),
                                "order": "date_from desc, create_date desc, id desc",
                            },
                        ),
                        ("name", {"label": _("Reference"), "order": "name asc, id desc"}),
                        (
                            "destination",
                            {
                                "label": _("Destination"),
                                "order": "destination asc, date_from desc, id desc",
                            },
                        ),
                        (
                            "state",
                            {
                                "label": _("Etat"),
                                "order": "state asc, date_from desc, id desc",
                            },
                        ),
                    ]
                ),
                "default_sortby": "date",
                "state_labels": self._get_request_state_labels("hr.travel.request"),
            },
            "supply": {
                "namespace": "supply",
                "model": "hr.supply.request",
                "list_route": "/my/supply_requests",
                "new_route": "/my/supply_requests/new",
                "submit_route": "/my/supply_requests/%s/submit",
                "history_key": "my_supply_requests_history",
                "record_key": "supply_request",
                "records_key": "supply_requests",
                "page_names": {
                    "list": "supply_requests",
                    "detail": "supply_request_detail",
                    "new": "supply_request_new",
                },
                "templates": {
                    "list": "portail_rh.portal_my_supply_requests",
                    "detail": "portail_rh.portal_supply_request_detail",
                    "new": "portail_rh.portal_new_supply_request",
                },
                "labels": {
                    "home_title": _("Mes fournitures"),
                    "list_title": _("Mes fournitures"),
                    "new_title": _("Nouvelle demande de fournitures"),
                    "empty": _("Aucune demande de fournitures pour le moment."),
                },
                "sortings": OrderedDict(
                    [
                        (
                            "date",
                            {
                                "label": _("Date de creation"),
                                "order": "create_date desc, id desc",
                            },
                        ),
                        ("name", {"label": _("Reference"), "order": "name asc, id desc"}),
                        ("item", {"label": _("Article"), "order": "item_name asc, id desc"}),
                        (
                            "state",
                            {
                                "label": _("Etat"),
                                "order": "state asc, create_date desc, id desc",
                            },
                        ),
                    ]
                ),
                "default_sortby": "date",
                "state_labels": self._get_request_state_labels("hr.supply.request"),
            },
        }
        return configs[request_type]

    def _get_request_domain(self, request_type):
        return [("employee_id.user_id", "=", request.env.user.id)]

    def _get_request_record(self, request_type, request_id):
        config = self._get_request_portal_config(request_type)
        portal_record = request.env[config["model"]].search(
            self._get_request_domain(request_type) + [("id", "=", request_id)],
            limit=1,
        )
        if not portal_record:
            raise NotFound()
        return portal_record

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        travel_model = request.env["hr.travel.request"]
        supply_model = request.env["hr.supply.request"]
        if "travel_request_count" in counters:
            values["travel_request_count"] = (
                travel_model.search_count(self._get_request_domain("travel"))
                if travel_model.check_access_rights("read", raise_exception=False)
                else 0
            )
        if "supply_request_count" in counters:
            values["supply_request_count"] = (
                supply_model.search_count(self._get_request_domain("supply"))
                if supply_model.check_access_rights("read", raise_exception=False)
                else 0
            )
        return values

    def _prepare_request_form_values(self, request_type, post=None):
        post = post or {}
        if request_type == "travel":
            return {
                "destination": post.get("destination", ""),
                "date_from": post.get("date_from", ""),
                "date_to": post.get("date_to", ""),
                "purpose": post.get("purpose", ""),
                "estimated_cost": post.get("estimated_cost", ""),
            }
        return {
            "item_name": post.get("item_name", ""),
            "description": post.get("description", ""),
            "quantity": post.get("quantity", "1"),
            "estimated_cost": post.get("estimated_cost", ""),
            "reason": post.get("reason", ""),
        }

    def _prepare_request_list_values(self, request_type, page=1, sortby=None, filterby=None):
        config = self._get_request_portal_config(request_type)
        portal_model = request.env[config["model"]]
        searchbar_sortings = config["sortings"]
        searchbar_filters = self._get_request_filters()

        if sortby not in searchbar_sortings:
            sortby = config["default_sortby"]
        if filterby not in searchbar_filters:
            filterby = "all"

        domain = self._get_request_domain(request_type) + searchbar_filters[filterby]["domain"]
        pager = portal_pager(
            url=config["list_route"],
            total=portal_model.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={"sortby": sortby, "filterby": filterby},
        )
        portal_records = portal_model.search(
            domain,
            order=searchbar_sortings[sortby]["order"],
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session[config["history_key"]] = portal_records.ids[:100]

        values = self._prepare_portal_layout_values()
        values.update(
            {
                "default_url": config["list_route"],
                "filterby": filterby,
                "page_name": config["page_names"]["list"],
                "pager": pager,
                "portal_empty_message": config["labels"]["empty"],
                "portal_list_title": config["labels"]["list_title"],
                "portal_new_route": config["new_route"],
                "portal_state_labels": config["state_labels"],
                "searchbar_filters": searchbar_filters,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
            }
        )
        values[config["records_key"]] = portal_records
        return values

    def _prepare_request_detail_values(
        self, request_type, portal_record, message_code=None, error_message=None
    ):
        config = self._get_request_portal_config(request_type)
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "error_message": error_message,
                "page_name": config["page_names"]["detail"],
                "portal_state_labels": config["state_labels"],
                "portal_submit_route": config["submit_route"],
                "success_message": self._get_portal_feedback_message(request_type, message_code),
            }
        )
        values[config["record_key"]] = portal_record
        return self._get_page_view_values(
            portal_record,
            access_token=None,
            values=values,
            session_history=config["history_key"],
            no_breadcrumbs=False,
        )

    def _prepare_request_create_values(self, request_type, employee, values):
        if request_type == "travel":
            destination = values["destination"].strip()
            return {
                "name": _("Deplacement - %s") % destination if destination else _("Nouvelle demande"),
                "employee_id": employee.id,
                "destination": destination,
                "date_from": values["date_from"],
                "date_to": values["date_to"],
                "purpose": values["purpose"],
                "estimated_cost": float(values["estimated_cost"] or 0.0),
                "state": "draft",
            }
        return {
            "employee_id": employee.id,
            "item_name": values["item_name"].strip(),
            "description": values["description"],
            "quantity": float(values["quantity"] or 1.0),
            "estimated_cost": float(values["estimated_cost"] or 0.0),
            "reason": values["reason"],
            "state": "draft",
        }

    def _render_request_form(self, request_type, form_values, error_message=None):
        config = self._get_request_portal_config(request_type)
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "employee": self._get_current_employee(),
                "error_message": error_message,
                "form_values": form_values,
                "page_name": config["page_names"]["new"],
                "portal_new_title": config["labels"]["new_title"],
            }
        )
        return request.render(config["templates"]["new"], values)

    @http.route(
        ["/my/travel_requests", "/my/travel_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_travel_requests(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_request_list_values(
            "travel",
            page=page,
            sortby=sortby,
            filterby=filterby,
        )
        values["success_message"] = self._get_portal_feedback_message("travel", kw.get("message"))
        return request.render("portail_rh.portal_my_travel_requests", values)

    @http.route("/my/travel_requests/new", type="http", auth="user", website=True)
    def portal_new_travel_request(self, **kw):
        return self._render_request_form(
            "travel",
            self._prepare_request_form_values("travel", kw),
            kw.get("error_message"),
        )

    @http.route("/my/travel_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_travel_request(self, **post):
        employee = self._get_current_employee()
        form_values = self._prepare_request_form_values("travel", post)
        try:
            portal_record = request.env["hr.travel.request"].create(
                self._prepare_request_create_values("travel", employee, form_values)
            )
        except (UserError, ValidationError, ValueError) as exc:
            return self._render_request_form("travel", form_values, str(exc))
        return request.redirect("/my/travel_requests/%s?message=created" % portal_record.id)

    @http.route("/my/travel_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_travel_request_detail(self, request_id, **kw):
        portal_record = self._get_request_record("travel", request_id)
        values = self._prepare_request_detail_values(
            "travel",
            portal_record,
            message_code=kw.get("message"),
            error_message=kw.get("error_message"),
        )
        return request.render("portail_rh.portal_travel_request_detail", values)

    @http.route(
        "/my/travel_requests/<int:request_id>/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_travel_request(self, request_id, **post):
        portal_record = self._get_request_record("travel", request_id)
        try:
            portal_record.action_submit()
        except (UserError, ValidationError) as exc:
            values = self._prepare_request_detail_values(
                "travel",
                portal_record,
                error_message=str(exc),
            )
            return request.render("portail_rh.portal_travel_request_detail", values)
        return request.redirect("/my/travel_requests/%s?message=submitted" % portal_record.id)

    @http.route(
        ["/my/supply_requests", "/my/supply_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_supply_requests(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_request_list_values(
            "supply",
            page=page,
            sortby=sortby,
            filterby=filterby,
        )
        values["success_message"] = self._get_portal_feedback_message("supply", kw.get("message"))
        return request.render("portail_rh.portal_my_supply_requests", values)

    @http.route("/my/supply_requests/new", type="http", auth="user", website=True)
    def portal_new_supply_request(self, **kw):
        return self._render_request_form(
            "supply",
            self._prepare_request_form_values("supply", kw),
            kw.get("error_message"),
        )

    @http.route("/my/supply_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_supply_request(self, **post):
        employee = self._get_current_employee()
        form_values = self._prepare_request_form_values("supply", post)
        try:
            portal_record = request.env["hr.supply.request"].create(
                self._prepare_request_create_values("supply", employee, form_values)
            )
        except (UserError, ValidationError, ValueError) as exc:
            return self._render_request_form("supply", form_values, str(exc))
        return request.redirect("/my/supply_requests/%s?message=created" % portal_record.id)

    @http.route("/my/supply_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_supply_request_detail(self, request_id, **kw):
        portal_record = self._get_request_record("supply", request_id)
        values = self._prepare_request_detail_values(
            "supply",
            portal_record,
            message_code=kw.get("message"),
            error_message=kw.get("error_message"),
        )
        return request.render("portail_rh.portal_supply_request_detail", values)

    @http.route(
        "/my/supply_requests/<int:request_id>/submit",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_submit_supply_request(self, request_id, **post):
        portal_record = self._get_request_record("supply", request_id)
        try:
            portal_record.action_submit()
        except (UserError, ValidationError) as exc:
            values = self._prepare_request_detail_values(
                "supply",
                portal_record,
                error_message=str(exc),
            )
            return request.render("portail_rh.portal_supply_request_detail", values)
        return request.redirect("/my/supply_requests/%s?message=submitted" % portal_record.id)
