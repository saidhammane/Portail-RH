from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrTravelRequest(models.Model):
    _name = "hr.travel.request"
    _description = "Demande de déplacement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)

    @api.model
    def _default_employee_id(self):
        employee = self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1)
        return employee.id or False

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employé",
        required=True,
        default=_default_employee_id,
    )
    can_approve = fields.Boolean(compute="_compute_can_approve", store=False)
    department_id = fields.Many2one(
        "hr.department",
        string="Département",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Manager",
        related="employee_id.parent_id",
        store=True,
        readonly=True,
    )
    destination = fields.Char(required=True)
    date_from = fields.Date(string="Date début", required=True)
    date_to = fields.Date(string="Date fin", required=True)
    duration_days = fields.Float(
        string="Durée (jours)",
        compute="_compute_duration_days",
        store=True,
    )
    purpose = fields.Text(string="Motif")
    estimated_cost = fields.Float(string="Coût estimé")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumis"),
            ("approved", "Approuvé"),
            ("rejected", "Refusé"),
            ("done", "Terminé"),
        ],
        default="draft",
        required=True,
    )

    def _is_rh_user(self):
        group = self.env.ref("portail_rh.group_portail_rh_hr", raise_if_not_found=False)
        return bool(group and self.env.user.has_group("portail_rh.group_portail_rh_hr"))

    @api.depends("manager_id", "manager_id.user_id")
    @api.depends_context("uid")
    def _compute_can_approve(self):
        current_user = self.env.user
        is_rh_user = self._is_rh_user()
        for record in self:
            record.can_approve = bool(
                is_rh_user or (record.manager_id.user_id and record.manager_id.user_id == current_user)
            )

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
                "summary": _("Valider la demande de déplacement"),
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
            activities.action_feedback(feedback=_("Demande traitée."))

    @api.depends("date_from", "date_to")
    def _compute_duration_days(self):
        for record in self:
            if record.date_from and record.date_to:
                record.duration_days = (record.date_to - record.date_from).days + 1
            else:
                record.duration_days = 0.0

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(
                    _("La date de fin doit être supérieure ou égale à la date de début.")
                )

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Seules les demandes en brouillon peuvent être soumises."))
        self.write({"state": "submitted"})
        self._create_manager_todo_activity()

    def action_approve(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'êtes pas autorisé à valider cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent être approuvées."))
        self.write({"state": "approved"})
        self._close_manager_todo_activity()

    def action_reject(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'êtes pas autorisé à valider cette demande."))
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent être refusées."))
        self.write({"state": "rejected"})
        self._close_manager_todo_activity()

    def action_done(self):
        self.ensure_one()
        if not self.can_approve:
            raise UserError(_("Vous n'êtes pas autorisé à valider cette demande."))
        if self.state != "approved":
            raise UserError(_("Seules les demandes approuvées peuvent être terminées."))
        self.write({"state": "done"})
        self._close_manager_todo_activity()

    def action_set_draft(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("La demande est déjà en brouillon."))
        current_user = self.env.user
        is_employee_owner = bool(self.employee_id.user_id and current_user == self.employee_id.user_id)
        is_manager = bool(self.manager_id.user_id and current_user == self.manager_id.user_id)
        is_rh_user = self._is_rh_user()

        if is_employee_owner:
            if self.state != "submitted":
                raise UserError(_("Impossible de remettre en brouillon après validation."))
        elif not (is_manager or is_rh_user):
            raise UserError(_("Vous n'êtes pas autorisé."))

        self.write({"state": "draft"})

    def write(self, vals):
        protected_fields = {
            "employee_id",
            "destination",
            "date_from",
            "date_to",
            "estimated_cost",
            "purpose",
            "name",
        }
        attempted_protected_fields = protected_fields.intersection(vals.keys())
        if attempted_protected_fields:
            is_rh_user = self._is_rh_user()
            current_user = self.env.user
            for record in self:
                is_manager = bool(record.manager_id.user_id and record.manager_id.user_id == current_user)
                if record.state != "draft" and not (is_manager or is_rh_user):
                    raise UserError(
                        _("Modification interdite après soumission. Contactez votre manager/RH.")
                    )

        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        default_employee_id = self._default_employee_id()
        for vals in vals_list:
            if not vals.get("employee_id") and default_employee_id:
                vals["employee_id"] = default_employee_id
        return super().create(vals_list)
