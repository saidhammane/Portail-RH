from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PortailRhTravelRequest(models.Model):
    _name = "portail.rh.travel.request"
    _description = "Travel Request"
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
    requester_user_id = fields.Many2one(
        "res.users",
        string="Requester",
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
    manager_user_id = fields.Many2one(
        "res.users",
        string="Approver",
        compute="_compute_manager_user_id",
        store=True,
        readonly=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    destination = fields.Char(string="Destination", required=True, tracking=True)
    date_start = fields.Date(string="Start Date", required=True, tracking=True)
    date_end = fields.Date(string="End Date", required=True, tracking=True)
    purpose = fields.Text(string="Purpose")
    transport_mode = fields.Selection(
        [
            ("car", "Car"),
            ("train", "Train"),
            ("plane", "Plane"),
            ("other", "Other"),
        ],
        string="Transport Mode",
        default="car",
        tracking=True,
    )
    estimated_cost = fields.Monetary(string="Estimated Cost", tracking=True)
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
        employee = self.env["hr.employee"].search([("user_id", "=", self.env.uid)], limit=1)
        return employee.id

    @api.depends("employee_id", "employee_id.parent_id.user_id")
    def _compute_manager_user_id(self):
        for record in self:
            record.manager_user_id = record.employee_id.parent_id.user_id

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code("portail.rh.travel.request") or "New"
        return super().create(vals_list)

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_("End Date must be greater than or equal to Start Date."))

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft requests can be submitted."))
        self.write({"state": "submitted"})

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted requests can be approved."))
        if not self.env.user.has_group("portail_rh_travel_request.group_travel_request_manager"):
            if self.manager_user_id != self.env.user:
                raise UserError(_("Only the assigned approver can approve this request."))
        self.write({"state": "approved"})

    def action_reject(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted requests can be rejected."))
        if not self.env.user.has_group("portail_rh_travel_request.group_travel_request_manager"):
            if self.manager_user_id != self.env.user:
                raise UserError(_("Only the assigned approver can reject this request."))
        self.write({"state": "rejected"})

    def action_set_draft(self):
        self.ensure_one()
        if self.state not in ("submitted", "approved", "rejected", "done"):
            raise UserError(_("Only non-draft requests can be reset to draft."))
        self.write({"state": "draft"})

    def action_done(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only approved requests can be marked as done."))
        self.write({"state": "done"})
