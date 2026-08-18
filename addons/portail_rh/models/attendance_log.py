from odoo import fields, models


class HrAttendanceDeviceLog(models.Model):
    _name = "hr.attendance.device.log"
    _description = "Log brut de pointage"
    _order = "punch_datetime desc, id desc"

    device_user_id = fields.Char(
        string="Identifiant utilisateur appareil",
        required=True,
        index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employe",
        index=True,
    )
    punch_datetime = fields.Datetime(
        string="Date et heure du pointage",
        required=True,
        index=True,
    )
    punch_type = fields.Selection(
        [
            ("check_in", "Entree"),
            ("check_out", "Sortie"),
            ("unknown", "Inconnu"),
        ],
        string="Type de pointage",
        required=True,
        default="unknown",
        index=True,
    )
    device_name = fields.Char(string="Nom de l'appareil")
    device_serial = fields.Char(string="Numero de serie", index=True)
    external_uid = fields.Char(string="Identifiant externe", index=True)
    state = fields.Selection(
        [
            ("raw", "Brut"),
            ("mapped", "Employe identifie"),
            ("processed", "Traite"),
            ("error", "Erreur"),
        ],
        string="Etat",
        required=True,
        default="raw",
        index=True,
    )
    error_message = fields.Text(string="Message d'erreur")
    company_id = fields.Many2one(
        "res.company",
        string="Societe",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "external_uid_device_serial_unique",
            "unique(external_uid, device_serial)",
            "Un log existe deja pour cet identifiant externe et cet appareil.",
        ),
    ]
