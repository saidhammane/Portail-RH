from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrOnboardingPlan(models.Model):
    _name = "hr.onboarding.plan"
    _description = "Plan d'integration"
    _order = "name"

    name = fields.Char(required=True)
    department_id = fields.Many2one("hr.department", string="Departement", index=True)
    job_id = fields.Many2one("hr.job", string="Poste", index=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        "hr.onboarding.plan.line",
        "plan_id",
        string="Etapes",
        copy=True,
    )


class HrOnboardingPlanLine(models.Model):
    _name = "hr.onboarding.plan.line"
    _description = "Etape du plan d'integration"
    _order = "sequence, id"

    plan_id = fields.Many2one(
        "hr.onboarding.plan",
        required=True,
        index=True,
        ondelete="cascade",
    )
    name = fields.Char(required=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)


class HrOnboardingEmployeeTask(models.Model):
    _name = "hr.onboarding.employee.task"
    _description = "Tache d'integration d'un employe"
    _order = "employee_id, plan_line_id"

    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        index=True,
        ondelete="cascade",
    )
    plan_line_id = fields.Many2one(
        "hr.onboarding.plan.line",
        required=True,
        index=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        [("todo", "A faire"), ("in_progress", "En cours"), ("done", "Terminee")],
        required=True,
        default="todo",
        index=True,
    )
    completed_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        (
            "employee_plan_line_unique",
            "unique(employee_id, plan_line_id)",
            "Cette etape existe deja pour cet employe.",
        )
    ]

    @api.model
    def ensure_for_employee(self, employee):
        plans = self.env["hr.onboarding.plan"].sudo().search([("active", "=", True)])
        plans = plans.filtered(
            lambda plan: (
                not plan.department_id or plan.department_id == employee.department_id
            )
            and (not plan.job_id or plan.job_id == employee.job_id)
        )
        existing_line_ids = set(
            self.sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("plan_line_id", "in", plans.line_ids.ids),
                ]
            )
            .mapped("plan_line_id")
            .ids
        )
        missing_values = [
            {"employee_id": employee.id, "plan_line_id": line.id}
            for line in plans.line_ids
            if line.id not in existing_line_ids
        ]
        if missing_values:
            self.sudo().create(missing_values)
        return self.search([("employee_id", "=", employee.id)])

    def write(self, values):
        if "state" in values:
            values["completed_at"] = (
                fields.Datetime.now() if values["state"] == "done" else False
            )
        return super().write(values)

    @api.constrains("employee_id", "plan_line_id")
    def _check_plan_scope(self):
        for task in self:
            plan = task.plan_line_id.plan_id
            if plan.department_id and task.employee_id.department_id != plan.department_id:
                raise ValidationError("Le plan ne correspond pas au departement de l'employe.")
            if plan.job_id and task.employee_id.job_id != plan.job_id:
                raise ValidationError("Le plan ne correspond pas au poste de l'employe.")
