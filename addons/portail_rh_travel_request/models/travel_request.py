from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrTravelRequest(models.Model):
    _name = "hr.travel.request"
    _description = "HR Travel Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        default=lambda self: self._default_employee_id(),
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        related="employee_id.user_id",
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
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
    mission_type = fields.Selection(
        [("internal", "Internal"), ("external", "External")],
        string="Mission Type",
        default="internal",
        required=True,
        tracking=True,
    )
    destination = fields.Char(string="Destination", required=True, tracking=True)
    purpose = fields.Text(string="Purpose")
    date_from = fields.Date(string="Date From", required=True, tracking=True)
    date_to = fields.Date(string="Date To", required=True, tracking=True)
    duration_days = fields.Float(
        string="Duration (Days)",
        compute="_compute_duration_days",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    estimated_cost = fields.Monetary(string="Estimated Cost", currency_field="currency_id")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.model
    def _default_employee_id(self):
        return self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1)

    @api.depends("date_from", "date_to")
    def _compute_duration_days(self):
        for record in self:
            if record.date_from and record.date_to:
                record.duration_days = (record.date_to - record.date_from + timedelta(days=1)).days
            else:
                record.duration_days = 0.0

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_("Date To must be greater than or equal to Date From."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code("hr.travel.request") or "New"
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft requests can be submitted."))
        self.write({"state": "submitted"})

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted requests can be approved."))
        self.write({"state": "approved"})

    def action_reject(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted requests can be rejected."))
        self.write({"state": "rejected"})

    def action_done(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only approved requests can be marked as done."))
        self.write({"state": "done"})

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Request is already in draft state."))
        self.write({"state": "draft"})
