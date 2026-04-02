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

    def _travel_request_domain(self):
        return [("employee_id.user_id", "=", request.env.user.id)]

    def _supply_request_domain(self):
        return [("employee_id.user_id", "=", request.env.user.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "travel_request_count" in counters:
            values["travel_request_count"] = request.env["hr.travel.request"].search_count(
                self._travel_request_domain()
            )
        if "supply_request_count" in counters:
            values["supply_request_count"] = request.env["hr.supply.request"].search_count(
                self._supply_request_domain()
            )
        return values

    def _prepare_travel_form_values(self, post=None):
        post = post or {}
        return {
            "destination": post.get("destination", ""),
            "date_from": post.get("date_from", ""),
            "date_to": post.get("date_to", ""),
            "purpose": post.get("purpose", ""),
            "estimated_cost": post.get("estimated_cost", ""),
        }

    def _prepare_supply_form_values(self, post=None):
        post = post or {}
        return {
            "item_name": post.get("item_name", ""),
            "description": post.get("description", ""),
            "quantity": post.get("quantity", "1"),
            "estimated_cost": post.get("estimated_cost", ""),
            "reason": post.get("reason", ""),
        }

    def _get_travel_request(self, request_id):
        travel_request = request.env["hr.travel.request"].search(
            self._travel_request_domain() + [("id", "=", request_id)],
            limit=1,
        )
        if not travel_request:
            raise NotFound()
        return travel_request

    def _get_supply_request(self, request_id):
        supply_request = request.env["hr.supply.request"].search(
            self._supply_request_domain() + [("id", "=", request_id)],
            limit=1,
        )
        if not supply_request:
            raise NotFound()
        return supply_request

    @http.route(
        ["/my/travel_requests", "/my/travel_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_travel_requests(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        TravelRequest = request.env["hr.travel.request"]
        domain = self._travel_request_domain()
        success_message = self._get_portal_feedback_message("travel", kw.get("message"))
        total = TravelRequest.search_count(domain)
        pager = portal_pager(
            url="/my/travel_requests",
            total=total,
            page=page,
            step=self._items_per_page,
            url_args=kw,
        )
        travel_requests = TravelRequest.search(
            domain,
            order="date_from desc, create_date desc, id desc",
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        values.update(
            {
                "page_name": "travel_requests",
                "travel_requests": travel_requests,
                "pager": pager,
                "success_message": success_message,
            }
        )
        return request.render("portail_rh.portal_my_travel_requests", values)

    @http.route("/my/travel_requests/new", type="http", auth="user", website=True)
    def portal_new_travel_request(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "page_name": "travel_request_new",
                "employee": self._get_current_employee(),
                "form_values": self._prepare_travel_form_values(kw),
                "error_message": kw.get("error_message"),
            }
        )
        return request.render("portail_rh.portal_new_travel_request", values)

    @http.route("/my/travel_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_travel_request(self, **post):
        employee = self._get_current_employee()
        values = self._prepare_travel_form_values(post)
        destination = values["destination"].strip()
        try:
            travel_request = request.env["hr.travel.request"].create(
                {
                    "name": _("Deplacement - %s") % destination if destination else _("Nouvelle demande"),
                    "employee_id": employee.id,
                    "destination": destination,
                    "date_from": values["date_from"],
                    "date_to": values["date_to"],
                    "purpose": values["purpose"],
                    "estimated_cost": float(values["estimated_cost"] or 0.0),
                    "state": "draft",
                }
            )
        except (UserError, ValidationError, ValueError) as exc:
            portal_values = self._prepare_portal_layout_values()
            portal_values.update(
                {
                    "page_name": "travel_request_new",
                    "employee": employee,
                    "form_values": values,
                    "error_message": str(exc),
                }
            )
            return request.render("portail_rh.portal_new_travel_request", portal_values)
        return request.redirect("/my/travel_requests/%s?message=created" % travel_request.id)

    @http.route("/my/travel_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_travel_request_detail(self, request_id, **kw):
        travel_request = self._get_travel_request(request_id)
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "page_name": "travel_request_detail",
                "travel_request": travel_request,
                "success_message": self._get_portal_feedback_message("travel", kw.get("message")),
                "error_message": kw.get("error_message"),
            }
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
        travel_request = self._get_travel_request(request_id)
        try:
            travel_request.action_submit()
        except (UserError, ValidationError) as exc:
            values = self._prepare_portal_layout_values()
            values.update(
                {
                    "page_name": "travel_request_detail",
                    "travel_request": travel_request,
                    "error_message": str(exc),
                }
            )
            return request.render("portail_rh.portal_travel_request_detail", values)
        return request.redirect("/my/travel_requests/%s?message=submitted" % travel_request.id)

    @http.route(
        ["/my/supply_requests", "/my/supply_requests/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_supply_requests(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        SupplyRequest = request.env["hr.supply.request"]
        domain = self._supply_request_domain()
        success_message = self._get_portal_feedback_message("supply", kw.get("message"))
        total = SupplyRequest.search_count(domain)
        pager = portal_pager(
            url="/my/supply_requests",
            total=total,
            page=page,
            step=self._items_per_page,
            url_args=kw,
        )
        supply_requests = SupplyRequest.search(
            domain,
            order="create_date desc, id desc",
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        values.update(
            {
                "page_name": "supply_requests",
                "supply_requests": supply_requests,
                "pager": pager,
                "success_message": success_message,
            }
        )
        return request.render("portail_rh.portal_my_supply_requests", values)

    @http.route("/my/supply_requests/new", type="http", auth="user", website=True)
    def portal_new_supply_request(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "page_name": "supply_request_new",
                "employee": self._get_current_employee(),
                "form_values": self._prepare_supply_form_values(kw),
                "error_message": kw.get("error_message"),
            }
        )
        return request.render("portail_rh.portal_new_supply_request", values)

    @http.route("/my/supply_requests/create", type="http", auth="user", website=True, methods=["POST"])
    def portal_create_supply_request(self, **post):
        employee = self._get_current_employee()
        values = self._prepare_supply_form_values(post)
        try:
            supply_request = request.env["hr.supply.request"].create(
                {
                    "employee_id": employee.id,
                    "item_name": values["item_name"].strip(),
                    "description": values["description"],
                    "quantity": float(values["quantity"] or 1.0),
                    "estimated_cost": float(values["estimated_cost"] or 0.0),
                    "reason": values["reason"],
                    "state": "draft",
                }
            )
        except (UserError, ValidationError, ValueError) as exc:
            portal_values = self._prepare_portal_layout_values()
            portal_values.update(
                {
                    "page_name": "supply_request_new",
                    "employee": employee,
                    "form_values": values,
                    "error_message": str(exc),
                }
            )
            return request.render("portail_rh.portal_new_supply_request", portal_values)
        return request.redirect("/my/supply_requests/%s?message=created" % supply_request.id)

    @http.route("/my/supply_requests/<int:request_id>", type="http", auth="user", website=True)
    def portal_supply_request_detail(self, request_id, **kw):
        supply_request = self._get_supply_request(request_id)
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "page_name": "supply_request_detail",
                "supply_request": supply_request,
                "success_message": self._get_portal_feedback_message("supply", kw.get("message")),
                "error_message": kw.get("error_message"),
            }
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
        supply_request = self._get_supply_request(request_id)
        try:
            supply_request.action_submit()
        except (UserError, ValidationError) as exc:
            values = self._prepare_portal_layout_values()
            values.update(
                {
                    "page_name": "supply_request_detail",
                    "supply_request": supply_request,
                    "error_message": str(exc),
                }
            )
            return request.render("portail_rh.portal_supply_request_detail", values)
        return request.redirect("/my/supply_requests/%s?message=submitted" % supply_request.id)
