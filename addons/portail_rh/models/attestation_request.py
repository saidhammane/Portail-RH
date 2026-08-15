from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class HrAttestationRequest(models.Model):
    _name = "hr.attestation.request"
    _description = "Demande d'attestation RH"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        default=lambda self: _("Nouveau"),
        tracking=True,
    )

    @api.model
    def _default_employee_id(self):
        employee = self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1)
        return employee.id or False

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employe",
        required=True,
        default=_default_employee_id,
        tracking=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Departement",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )
    attestation_type = fields.Selection(
        [
            ("work", "Attestation de travail"),
            ("salary", "Attestation de salaire"),
            ("internship", "Attestation de stage"),
            ("other", "Autre"),
        ],
        string="Type d'attestation",
        required=True,
        tracking=True,
    )
    reason = fields.Text(string="Motif")
    request_date = fields.Date(
        string="Date de demande",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumis"),
            ("approved", "Approuve"),
            ("rejected", "Refuse"),
            ("done", "Termine"),
        ],
        string="Etat",
        required=True,
        default="draft",
        tracking=True,
    )
    can_approve = fields.Boolean(compute="_compute_can_approve")

    def _is_rh_user(self):
        return self.env.user.has_group("portail_rh.group_portail_rh_hr")

    @api.depends_context("uid")
    def _compute_can_approve(self):
        can_approve = self._is_rh_user()
        for record in self:
            record.can_approve = can_approve

    @api.model_create_multi
    def create(self, vals_list):
        default_employee_id = self._default_employee_id()
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not self._is_rh_user():
                vals["state"] = "draft"
            if not vals.get("employee_id") and default_employee_id:
                vals["employee_id"] = default_employee_id
            if not vals.get("name") or vals["name"] == _("Nouveau"):
                vals["name"] = sequence.next_by_code("hr.attestation.request") or _("Nouveau")
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Seules les demandes en brouillon peuvent etre soumises."))
        self.with_context(attestation_workflow=True).write({"state": "submitted"})

    def action_approve(self):
        self.ensure_one()
        if not self._is_rh_user():
            raise UserError(_("Seul le service RH peut approuver cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent etre approuvees."))
        self.with_context(attestation_workflow=True).write({"state": "approved"})

    def action_reject(self):
        self.ensure_one()
        if not self._is_rh_user():
            raise UserError(_("Seul le service RH peut refuser cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent etre refusees."))
        self.with_context(attestation_workflow=True).write({"state": "rejected"})

    def action_done(self):
        self.ensure_one()
        if not self._is_rh_user():
            raise UserError(_("Seul le service RH peut terminer cette demande."))
        if self.state != "approved":
            raise UserError(_("Seules les demandes approuvees peuvent etre terminees."))
        self.with_context(attestation_workflow=True).write({"state": "done"})

    def action_set_draft(self):
        self.ensure_one()
        if self.state not in ("submitted", "rejected"):
            raise UserError(
                _("Seules les demandes soumises ou refusees peuvent revenir en brouillon.")
            )
        self.with_context(attestation_workflow=True).write({"state": "draft"})

    def _check_attestation_print_access(self):
        self.check_access_rights("read")
        self.check_access_rule("read")
        is_rh_user = self._is_rh_user()
        for record in self:
            if record.state not in ("approved", "done"):
                raise UserError(
                    _("Seules les attestations approuvees ou terminees peuvent etre imprimees.")
                )
            if not is_rh_user and record.employee_id.user_id != self.env.user:
                raise AccessError(_("Vous ne pouvez imprimer que vos propres attestations."))
        return True

    def action_print_attestation(self):
        self.ensure_one()
        self._check_attestation_print_access()
        return self.env.ref("portail_rh.action_report_hr_attestation").report_action(self)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("attestation_workflow"):
            raise UserError(_("Utilisez les boutons du workflow pour modifier l'etat."))

        protected_fields = {"employee_id", "attestation_type", "reason", "request_date"}
        if protected_fields.intersection(vals) and not self._is_rh_user():
            for record in self:
                if record.state != "draft":
                    raise UserError(
                        _("Modification interdite apres soumission. Contactez le service RH.")
                    )
        return super().write(vals)


class ReportHrAttestationRequest(models.AbstractModel):
    _name = "report.portail_rh.report_attestation_document"
    _description = "Rapport attestation RH"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["hr.attestation.request"].browse(docids).exists()
        if len(docs) != len(docids):
            raise AccessError(_("Une ou plusieurs attestations sont introuvables."))
        docs._check_attestation_print_access()
        return {
            "doc_ids": docs.ids,
            "doc_model": "hr.attestation.request",
            "docs": docs,
        }
