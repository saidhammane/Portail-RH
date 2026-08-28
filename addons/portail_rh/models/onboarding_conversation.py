from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HrOnboardingConversation(models.Model):
    _name = "hr.onboarding.conversation"
    _description = "Conversation d'integration"
    _order = "last_message_at desc, id desc"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        index=True,
        ondelete="cascade",
    )
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    last_message_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    active = fields.Boolean(default=True)
    message_ids = fields.One2many(
        "hr.onboarding.message",
        "conversation_id",
        string="Messages",
    )

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.su:
            employee = self.env["hr.employee"].search(
                [("user_id", "=", self.env.uid)], limit=1
            )
            if not employee:
                raise AccessError("Aucun employe n'est associe a cet utilisateur.")
            for values in values_list:
                values["user_id"] = self.env.uid
                values["employee_id"] = employee.id
        return super().create(values_list)

    def write(self, values):
        if not self.env.su and {"user_id", "employee_id"} & set(values):
            raise AccessError("Le proprietaire d'une conversation ne peut pas etre modifie.")
        return super().write(values)


class HrOnboardingMessage(models.Model):
    _name = "hr.onboarding.message"
    _description = "Message d'integration"
    _order = "id"

    conversation_id = fields.Many2one(
        "hr.onboarding.conversation",
        required=True,
        index=True,
        ondelete="cascade",
    )
    role = fields.Selection(
        [("user", "Utilisateur"), ("assistant", "Assistant")],
        required=True,
        index=True,
    )
    content = fields.Text(required=True)
    source_document_ids = fields.Many2many(
        "hr.onboarding.document",
        "hr_onboarding_message_document_rel",
        "message_id",
        "document_id",
        string="Sources",
        readonly=True,
    )
    confidence_score = fields.Float(readonly=True)
    latency_ms = fields.Integer(readonly=True)
    cache_hit = fields.Boolean(readonly=True)
    feedback = fields.Selection(
        [("helpful", "Utile"), ("not_helpful", "Pas utile")],
    )
    source_payload = fields.Text(readonly=True)
    needs_escalation = fields.Boolean(readonly=True)
    escalated_at = fields.Datetime(readonly=True)
    escalation_activity_id = fields.Many2one(
        "mail.activity",
        readonly=True,
        ondelete="set null",
    )

    @api.constrains("confidence_score")
    def _check_confidence_score(self):
        for message in self:
            if not 0.0 <= message.confidence_score <= 1.0:
                raise ValidationError("Le score de confiance doit etre compris entre 0 et 1.")
