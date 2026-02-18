from odoo import models, fields


class MyModel(models.Model):
    _name = "my.model"
    _description = "My Model"

    name = fields.Char(required=True)
    note = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("confirmed", "Confirmé"),
            ("done", "Validé"),
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
