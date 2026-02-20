from odoo import fields, models


class MyModel(models.Model):
    _name = "my.model"
    _description = "Mon modele"

    name = fields.Char(required=True)
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("confirmed", "Confirme"),
            ("done", "Valide"),
        ],
        default="draft",
    )

    def action_confirm(self):
        self.ensure_one()
        self.write({"state": "confirmed"})

    def action_done(self):
        self.ensure_one()
        self.write({"state": "done"})

    def action_set_draft(self):
        self.ensure_one()
        self.write({"state": "draft"})
