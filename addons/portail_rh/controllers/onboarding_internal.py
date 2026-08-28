import hmac
import json
import os

from odoo import fields, http
from odoo.http import request


class OnboardingInternalController(http.Controller):
    @http.route(
        "/portail_rh/onboarding/index/callback",
        type="http",
        auth="none",
        csrf=False,
        methods=["POST"],
    )
    def indexing_callback(self):
        supplied = request.httprequest.headers.get("X-Service-Token", "")
        expected = os.getenv("ONBOARDING_AI_SERVICE_TOKEN", "")
        if not supplied or not expected or not hmac.compare_digest(supplied, expected):
            return request.make_json_response({"error": "unauthorized"}, status=401)
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True))
            document_id = int(payload["document_id"])
            checksum = str(payload["checksum"])
            state = payload["state"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return request.make_json_response({"error": "invalid_payload"}, status=400)
        if state not in {"processing", "indexed", "error"}:
            return request.make_json_response({"error": "invalid_state"}, status=400)

        document = request.env["hr.onboarding.document"].sudo().browse(document_id)
        if not document.exists():
            return request.make_json_response({"error": "not_found"}, status=404)
        if not hmac.compare_digest(document.checksum or "", checksum):
            return request.make_json_response({"status": "stale"}, status=202)

        values = {"indexing_state": state}
        if state == "indexed":
            values.update(
                {"indexed_at": fields.Datetime.now(), "error_message": False}
            )
        elif state == "error":
            values.update(
                {
                    "indexed_at": False,
                    "error_message": str(payload.get("error_message") or "Erreur d'indexation")[:500],
                }
            )
        document.with_context(onboarding_internal=True).write(values)
        return request.make_json_response({"status": "ok"})
