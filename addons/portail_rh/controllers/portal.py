from collections import OrderedDict

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


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

    def _state_labels(self, model_name):
        return dict(request.env[model_name].fields_get(["state"])["state"]["selection"])

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
        return OrderedDict(
            [
                ("date", {"label": _("Date de creation"), "order": "create_date desc, id desc"}),
                ("name", common["name"]),
                ("item", {"label": _("Article"), "order": "item_name asc, id desc"}),
                ("state", common["state"]),
            ]
        )

    def _feedback_message(self, request_type, code):
        return {
            ("travel", "created"): _("Votre demande de deplacement a ete creee en brouillon."),
            ("travel", "submitted"): _("Votre demande de deplacement a ete soumise."),
            ("supply", "created"): _("Votre demande de fournitures a ete creee en brouillon."),
            ("supply", "submitted"): _("Votre demande de fournitures a ete soumise."),
        }.get((request_type, code))

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        for request_type, counter in (
            ("travel", "travel_request_count"),
            ("supply", "supply_request_count"),
        ):
            if counter not in counters:
                continue
            model = request.env[self.REQUEST_CONFIG[request_type]["model"]]
            values[counter] = (
                model.search_count(self._request_domain())
                if model.check_access_rights("read", raise_exception=False)
                else 0
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
        return {
            "employee_id": employee.id,
            "item_name": values["item_name"].strip(),
            "description": values["description"],
            "quantity": float(values["quantity"] or 1),
            "estimated_cost": float(values["estimated_cost"] or 0),
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
