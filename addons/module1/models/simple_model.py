from odoo import models, fields

class MyModel(models.Model):
    _name = "my.model"
    _description = "My Model"

    name = fields.Char(required=True)
    note = fields.Text()
