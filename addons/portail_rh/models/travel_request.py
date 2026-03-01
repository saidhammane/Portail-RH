from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrTravelRequest(models.Model):
    _name = "hr.travel.request"
    _description = "Demande de déplacement"

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

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent être approuvées."))
        self.write({"state": "approved"})

    def action_reject(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Seules les demandes soumises peuvent être refusées."))
        self.write({"state": "rejected"})

    def action_done(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Seules les demandes approuvées peuvent être terminées."))
        self.write({"state": "done"})

    def action_set_draft(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("La demande est déjà en brouillon."))
        self.write({"state": "draft"})

    @api.model_create_multi
    def create(self, vals_list):
        default_employee_id = self._default_employee_id()
        for vals in vals_list:
            if not vals.get("employee_id") and default_employee_id:
                vals["employee_id"] = default_employee_id
        return super().create(vals_list)
