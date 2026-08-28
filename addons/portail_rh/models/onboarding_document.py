import base64
import hashlib
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


LOGGER = logging.getLogger(__name__)


class HrOnboardingDocument(models.Model):
    _name = "hr.onboarding.document"
    _description = "Document d'integration"
    _order = "name, version desc"

    name = fields.Char(string="Titre", required=True, index=True)
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Piece jointe technique",
        required=True,
        ondelete="restrict",
    )
    file_name = fields.Char(string="Nom du fichier")
    file_data = fields.Binary(
        string="Fichier",
        compute="_compute_file_data",
        inverse="_inverse_file_data",
    )
    category = fields.Selection(
        [
            ("welcome", "Accueil"),
            ("policy", "Politique interne"),
            ("benefits", "Avantages"),
            ("safety", "Sante et securite"),
            ("it", "Informatique"),
            ("other", "Autre"),
        ],
        required=True,
        default="welcome",
        index=True,
    )
    language = fields.Selection(
        [("fr", "Francais"), ("ar", "Arabe"), ("en", "Anglais")],
        required=True,
        default="fr",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Departement",
        domain="[('company_id', 'in', (False, company_id))]",
        index=True,
    )
    visibility = fields.Selection(
        [
            ("employee", "Tous les employes"),
            ("department", "Departement"),
            ("manager", "Managers"),
            ("hr", "RH uniquement"),
        ],
        required=True,
        default="employee",
        index=True,
    )
    version = fields.Integer(required=True, default=1, readonly=True)
    checksum = fields.Char(readonly=True, copy=False, index=True)
    indexing_state = fields.Selection(
        [
            ("pending", "En attente"),
            ("processing", "En cours"),
            ("indexed", "Indexe"),
            ("error", "Erreur"),
        ],
        required=True,
        default="pending",
        readonly=True,
        copy=False,
        index=True,
    )
    indexed_at = fields.Datetime(readonly=True, copy=False)
    error_message = fields.Text(readonly=True, copy=False)
    active = fields.Boolean(default=True)

    @api.depends("attachment_id", "attachment_id.datas")
    def _compute_file_data(self):
        for document in self:
            document.file_data = document.attachment_id.datas

    def _inverse_file_data(self):
        for document in self:
            if document.attachment_id and document.file_data:
                document.attachment_id.write(
                    {
                        "datas": document.file_data,
                        "name": document.file_name or document.attachment_id.name,
                    }
                )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            values.update(
                {
                    "version": 1,
                    "indexing_state": "pending",
                    "indexed_at": False,
                    "error_message": False,
                }
            )
            file_data = values.pop("file_data", False)
            if file_data and not values.get("attachment_id"):
                attachment = self.env["ir.attachment"].create(
                    {
                        "name": values.get("file_name") or values.get("name") or "document",
                        "datas": file_data,
                        "res_model": self._name,
                    }
                )
                values["attachment_id"] = attachment.id
            if values.get("attachment_id") and not values.get("file_name"):
                values["file_name"] = self.env["ir.attachment"].browse(
                    values["attachment_id"]
                ).name
        documents = super().create(values_list)
        for document in documents:
            if document.attachment_id and not document.attachment_id.res_id:
                document.attachment_id.write(
                    {"res_model": document._name, "res_id": document.id}
                )
            document.with_context(onboarding_internal=True).write(
                {"checksum": document._content_checksum()}
            )
        if not self.env.context.get("onboarding_skip_enqueue"):
            documents._schedule_indexing()
        return documents

    def write(self, values):
        indexing_fields = {
            "attachment_id",
            "file_data",
            "file_name",
            "name",
            "category",
            "language",
            "company_id",
            "department_id",
            "visibility",
            "active",
        }
        should_index = bool(indexing_fields & set(values)) and not self.env.context.get(
            "onboarding_internal"
        )
        if not self.env.context.get("onboarding_internal"):
            for protected in (
                "version",
                "checksum",
                "indexing_state",
                "indexed_at",
                "error_message",
            ):
                values.pop(protected, None)
        file_data = values.pop("file_data", False)
        result = super().write(values)
        if file_data:
            for document in self:
                document.attachment_id.write(
                    {
                        "datas": file_data,
                        "name": document.file_name or document.attachment_id.name,
                    }
                )
        if should_index:
            for document in self:
                document.with_context(onboarding_internal=True).write(
                    {
                        "version": document.version + 1,
                        "checksum": document._content_checksum(),
                        "indexing_state": "pending",
                        "indexed_at": False,
                        "error_message": False,
                    }
                )
            self._schedule_indexing()
        return result

    def _content_checksum(self):
        self.ensure_one()
        encoded = self.attachment_id.datas or b""
        if isinstance(encoded, str):
            encoded = encoded.encode("ascii")
        return hashlib.sha256(base64.b64decode(encoded)).hexdigest()

    def _index_payload(self):
        self.ensure_one()
        encoded = self.attachment_id.datas or b""
        if isinstance(encoded, bytes):
            encoded = encoded.decode("ascii")
        return {
            "document_id": self.id,
            "title": self.name,
            "filename": self.file_name or self.attachment_id.name,
            "content_base64": encoded,
            "category": self.category,
            "company_id": self.company_id.id,
            "department_id": self.department_id.id or None,
            "visibility": self.visibility,
            "version": self.version,
            "checksum": self.checksum,
            "language": self.language,
        }

    @api.model
    def _dispatch_index_job(self, payload):
        service_url = os.getenv("ONBOARDING_AI_URL", "").rstrip("/")
        service_token = os.getenv("ONBOARDING_AI_SERVICE_TOKEN")
        if not service_url or not service_token:
            LOGGER.warning("Onboarding indexing is pending: service configuration is missing")
            return False
        http_request = Request(
            service_url + "/v1/index/jobs",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Service-Token": service_token,
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=15) as response:
                return response.status == 202
        except (HTTPError, URLError, TimeoutError) as error:
            LOGGER.warning("Onboarding indexing dispatch failed: %s", type(error).__name__)
            return False

    def _schedule_indexing(self):
        for document in self.filtered("active"):
            payload = document._index_payload()
            self.env.cr.postcommit.add(
                lambda payload=payload: self._dispatch_index_job(payload)
            )

    def action_reindex(self):
        self.ensure_one()
        if not os.getenv("ONBOARDING_AI_URL") or not os.getenv(
            "ONBOARDING_AI_SERVICE_TOKEN"
        ):
            raise UserError("Le service d'indexation n'est pas configure.")
        self.with_context(onboarding_internal=True).write(
            {"indexing_state": "pending", "indexed_at": False, "error_message": False}
        )
        self._schedule_indexing()
        return True

    @api.constrains("attachment_id")
    def _check_supported_file(self):
        allowed_extensions = (".pdf", ".docx", ".txt")
        for document in self:
            name = (document.file_name or document.attachment_id.name or "").lower()
            if not name.endswith(allowed_extensions):
                raise ValidationError("Formats acceptes : PDF, DOCX et TXT.")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    onboarding_document_ids = fields.One2many(
        "hr.onboarding.document",
        "attachment_id",
        string="Documents d'integration",
    )
