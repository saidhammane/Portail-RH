from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrSupplyRequest(models.Model):
    _name = "hr.supply.request"
    _description = "Demande de fournitures"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Reference", required=True, default=lambda self: _("Nouveau"), tracking=True)

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
    manager_id = fields.Many2one(
        "hr.employee",
        string="Manager",
        related="department_id.manager_id",
        store=True,
        readonly=True,
    )
    item_name = fields.Char(string="Article", required=True, tracking=True)
    description = fields.Text(string="Description")
    quantity = fields.Float(string="Quantite", default=1.0, required=True, tracking=True)
    estimated_cost = fields.Float(string="Cout estime", default=0.0, tracking=True)
    reason = fields.Text(string="Motif")
    company_id = fields.Many2one(
        "res.company",
        string="Societe",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
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
        default="draft",
        required=True,
        tracking=True,
    )
    can_approve = fields.Boolean(compute="_compute_can_approve", store=False)

    def _is_rh_user(self):
        group = self.env.ref("portail_rh.group_portail_rh_hr", raise_if_not_found=False)
        return bool(
            self.env.su
            or (group and self.env.user.has_group("portail_rh.group_portail_rh_hr"))
        )

    @api.depends("manager_id", "manager_id.user_id")
    @api.depends_context("uid")
    def _compute_can_approve(self):
        current_user = self.env.user
        is_rh_user = self._is_rh_user()
        for record in self:
            record.can_approve = bool(
                is_rh_user or (record.manager_id.user_id and record.manager_id.user_id == current_user)
            )

    @api.constrains("quantity")
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("La quantite doit etre strictement positive."))

    @api.constrains("estimated_cost")
    def _check_estimated_cost(self):
        for record in self:
            if record.estimated_cost < 0:
                raise ValidationError(_("Le cout estime ne peut pas etre negatif."))

    def _create_manager_todo_activity(self):
        self.ensure_one()
        manager_user = self.manager_id.user_id
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not manager_user or not todo_type:
            return

        model_id = self.env["ir.model"]._get_id(self._name)
        existing = self.env["mail.activity"].search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", self.id),
                ("user_id", "=", manager_user.id),
                ("activity_type_id", "=", todo_type.id),
            ],
            limit=1,
        )
        if existing:
            return

        self.env["mail.activity"].create(
            {
                "res_model_id": model_id,
                "res_id": self.id,
                "user_id": manager_user.id,
                "activity_type_id": todo_type.id,
                "summary": _("Valider la demande de fournitures"),
                "note": _("Merci d'approuver ou refuser cette demande."),
            }
        )

    def _close_manager_todo_activity(self):
        self.ensure_one()
        manager_user = self.manager_id.user_id
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not manager_user or not todo_type:
            return

        model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", self.id),
                ("user_id", "=", manager_user.id),
                ("activity_type_id", "=", todo_type.id),
            ]
        )
        if activities:
            activities.action_feedback(feedback=_("Demande traitee."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence_model = self.env["ir.sequence"]
        default_employee_id = self._default_employee_id()
        for vals in vals_list:
            if not self._is_rh_user():
                vals["state"] = "draft"
            if not vals.get("employee_id") and default_employee_id:
                vals["employee_id"] = default_employee_id
            if not vals.get("name") or vals["name"] == _("Nouveau"):
                vals["name"] = sequence_model.next_by_code("hr.supply.request") or _("Nouveau")
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Seules les demandes en brouillon peuvent etre soumises."))
        self.with_context(portail_rh_workflow=True).write({"state": "submitted"})
        self._create_manager_todo_activity()

    def action_approve(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'etes pas autorise a approuver cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent etre approuvees."))
        self.with_context(portail_rh_workflow=True).write({"state": "approved"})
        self._close_manager_todo_activity()

    def action_reject(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'etes pas autorise a refuser cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent etre refusees."))
        self.with_context(portail_rh_workflow=True).write({"state": "rejected"})
        self._close_manager_todo_activity()

    def action_set_draft(self):
        self.ensure_one()
        if self.state not in ("submitted", "rejected"):
            raise UserError(_("Seules les demandes soumises ou refusees peuvent revenir en brouillon."))
        self.with_context(portail_rh_workflow=True).write({"state": "draft"})

    def action_done(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'etes pas autorise a terminer cette demande."))
        if self.state != "approved":
            raise UserError(_("Seules les demandes approuvees peuvent etre terminees."))
        self.with_context(portail_rh_workflow=True).write({"state": "done"})

    def write(self, vals):
        if "state" in vals and not self.env.context.get("portail_rh_workflow"):
            raise UserError(_("Utilisez les boutons du workflow pour modifier l'etat."))

        protected_fields = {
            "name",
            "employee_id",
            "item_name",
            "description",
            "quantity",
            "estimated_cost",
            "reason",
            "company_id",
        }
        attempted_protected_fields = protected_fields.intersection(vals.keys())
        if attempted_protected_fields:
            for record in self:
                if (
                    record.state != "draft"
                    and self.env.user.has_group("portail_rh.group_portail_rh_employee")
                    and not record.can_approve
                ):
                    raise UserError(
                        _("Modification interdite apres soumission. Contactez votre manager/RH.")
                    )

        return super().write(vals)
