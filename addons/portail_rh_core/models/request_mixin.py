from odoo import _, fields, models
from odoo.exceptions import UserError


class RhPortalRequestMixin(models.AbstractModel):
    _name = "rh.portal.request.mixin"
    _description = "RH Portal Request Mixin"

    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumis"),
            ("approved", "Approuve"),
            ("rejected", "Rejete"),
            ("done", "Termine"),
        ],
        string="Statut",
        default="draft",
        required=True,
        index=True,
    )

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Transition invalide: soumission autorisee uniquement depuis Brouillon."))
        self.write({"state": "submitted"})

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Transition invalide: approbation autorisee uniquement depuis Soumis."))
        self.write({"state": "approved"})

    def action_reject(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Transition invalide: rejet autorise uniquement depuis Soumis."))
        self.write({"state": "rejected"})

    def action_set_draft(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Transition invalide: l'enregistrement est deja en Brouillon."))
        if self.state not in ("submitted", "approved", "rejected", "done"):
            raise UserError(
                _(
                    "Transition invalide: retour en Brouillon autorise depuis Soumis, "
                    "Approuve, Rejete ou Termine."
                )
            )
        self.write({"state": "draft"})

    def action_done(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Transition invalide: cloture autorisee uniquement depuis Approuve."))
        self.write({"state": "done"})
