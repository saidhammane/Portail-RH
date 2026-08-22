import json
import os
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from odoo import _, fields, models
from odoo.exceptions import UserError


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

    @staticmethod
    def _zkteco_get_json(api_url, api_key, endpoint):
        request = Request(
            "%s%s" % (api_url.rstrip("/"), endpoint),
            headers={"Accept": "application/json", "X-API-Key": api_key},
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, ValueError) as error:
            raise UserError(_("Impossible de joindre le simulateur ZKTeco : %s") % error) from error

    @staticmethod
    def _zkteco_datetime(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    def action_import_zkteco_mock(self):
        """Import raw mock-device punches, safely retryable through external UIDs."""
        if not self.env.user.has_group("portail_rh.group_portail_rh_hr") and not self.env.user.has_group(
            "base.group_system"
        ):
            raise UserError(_("Seuls les utilisateurs RH peuvent importer les pointages ZKTeco."))

        api_url = os.getenv("ZKTECO_API_URL", "http://zkteco-mock:8090")
        api_key = os.getenv("ZKTECO_API_KEY", "zkteco-demo-key")
        employees = self._zkteco_get_json(api_url, api_key, "/api/v1/employees")["data"]
        devices = self._zkteco_get_json(api_url, api_key, "/api/v1/devices")["data"]
        employee_by_device_id = {}
        for source_employee in employees:
            employee = self.env["hr.employee"].search(
                [("work_email", "=", source_employee["email"])], limit=1
            )
            if employee:
                employee_by_device_id[source_employee["device_user_id"]] = employee.id
        device_names = {device["serial_number"]: device["name"] for device in devices}

        Log = self.sudo()
        after_id = 0
        imported_count = 0
        duplicate_count = 0
        unmatched_count = 0
        while True:
            payload = self._zkteco_get_json(
                api_url, api_key, "/api/v1/punches?after_id=%s&limit=500" % after_id
            )
            punches = payload["data"]
            if not punches:
                break
            for punch in punches:
                duplicate = Log.search_count(
                    [
                        ("external_uid", "=", punch["external_uid"]),
                        ("device_serial", "=", punch["device_serial"]),
                    ]
                )
                if duplicate:
                    duplicate_count += 1
                    continue
                employee_id = employee_by_device_id.get(punch["device_user_id"])
                values = {
                    "device_user_id": punch["device_user_id"],
                    "employee_id": employee_id,
                    "punch_datetime": self._zkteco_datetime(punch["punch_datetime_utc"]),
                    "punch_type": punch["punch_type"],
                    "device_name": device_names.get(punch["device_serial"], punch["device_serial"]),
                    "device_serial": punch["device_serial"],
                    "external_uid": punch["external_uid"],
                    "state": "mapped" if employee_id else "error",
                    "error_message": False if employee_id else _("Employe Odoo introuvable."),
                }
                Log.create(values)
                imported_count += 1
                unmatched_count += not bool(employee_id)
            if not payload["pagination"]["has_more"]:
                break
            after_id = payload["pagination"]["next_after_id"]

        message = _(
            "Import ZKTeco termine : %(imported)s nouveau(x) pointage(s), "
            "%(duplicates)s doublon(s) ignore(s), %(unmatched)s employe(s) non associe(s)."
        ) % {
            "imported": imported_count,
            "duplicates": duplicate_count,
            "unmatched": unmatched_count,
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("ZKTeco"), "message": message, "type": "success", "sticky": False},
        }
