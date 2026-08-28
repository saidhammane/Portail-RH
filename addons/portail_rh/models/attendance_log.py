import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    zkteco_user_id = fields.Char(
        string="Identifiant ZKTeco",
        copy=False,
        index=True,
        groups="portail_rh.group_portail_rh_hr,base.group_system",
    )

    _sql_constraints = [
        (
            "zkteco_user_company_unique",
            "unique(zkteco_user_id, company_id)",
            "Cet identifiant ZKTeco est deja utilise dans cette societe.",
        ),
    ]


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    zkteco_managed = fields.Boolean(
        string="Importe depuis ZKTeco",
        default=False,
        copy=False,
        index=True,
    )
    zkteco_log_ids = fields.One2many(
        "hr.attendance.device.log",
        "attendance_id",
        string="Logs ZKTeco",
        readonly=True,
    )
    zkteco_late_minutes = fields.Integer(
        string="Retard (minutes)",
        compute="_compute_zkteco_indicators",
        store=True,
    )
    zkteco_early_departure_minutes = fields.Integer(
        string="Depart anticipe (minutes)",
        compute="_compute_zkteco_indicators",
        store=True,
    )
    zkteco_status = fields.Selection(
        [
            ("on_time", "A l'heure"),
            ("late", "En retard"),
            ("early", "Depart anticipe"),
            ("late_early", "Retard et depart anticipe"),
        ],
        string="Statut ZKTeco",
        compute="_compute_zkteco_indicators",
        store=True,
        index=True,
    )

    @staticmethod
    def _zkteco_local_datetime(value):
        device_timezone = os.getenv("ZKTECO_TIMEZONE", "Africa/Casablanca")
        return pytz.UTC.localize(value).astimezone(pytz.timezone(device_timezone))

    @api.depends(
        "zkteco_managed",
        "employee_id",
        "check_in",
        "check_out",
        "employee_id.resource_calendar_id.attendance_ids.dayofweek",
        "employee_id.resource_calendar_id.attendance_ids.hour_from",
        "employee_id.resource_calendar_id.attendance_ids.hour_to",
    )
    def _compute_zkteco_indicators(self):
        for attendance in self:
            attendance.zkteco_late_minutes = 0
            attendance.zkteco_early_departure_minutes = 0
            attendance.zkteco_status = False
            if not attendance.zkteco_managed or not attendance.employee_id or not attendance.check_in:
                continue

            employee = attendance.employee_id
            calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
            if not calendar:
                attendance.zkteco_status = "on_time"
                continue

            local_check_in = self._zkteco_local_datetime(attendance.check_in)
            local_date = local_check_in.date()
            schedule_lines = calendar.attendance_ids.filtered(
                lambda line: line.dayofweek == str(local_check_in.weekday())
                and line.day_period != "lunch"
                and (not line.date_from or line.date_from <= local_date)
                and (not line.date_to or line.date_to >= local_date)
            )
            if not schedule_lines:
                attendance.zkteco_status = "on_time"
                continue

            start_hour = min(schedule_lines.mapped("hour_from"))
            end_hour = max(schedule_lines.mapped("hour_to"))
            check_in_hour = local_check_in.hour + local_check_in.minute / 60.0
            late_minutes = max(0, round((check_in_hour - start_hour) * 60))
            early_minutes = 0
            if attendance.check_out:
                local_check_out = self._zkteco_local_datetime(attendance.check_out)
                check_out_hour = local_check_out.hour + local_check_out.minute / 60.0
                early_minutes = max(0, round((end_hour - check_out_hour) * 60))

            attendance.zkteco_late_minutes = late_minutes
            attendance.zkteco_early_departure_minutes = early_minutes
            if late_minutes and early_minutes:
                attendance.zkteco_status = "late_early"
            elif late_minutes:
                attendance.zkteco_status = "late"
            elif early_minutes:
                attendance.zkteco_status = "early"
            else:
                attendance.zkteco_status = "on_time"


class HrAttendanceDeviceLog(models.Model):
    _name = "hr.attendance.device.log"
    _description = "Log brut de pointage"
    _order = "punch_datetime desc, id desc"

    device_user_id = fields.Char(
        string="Identifiant utilisateur appareil",
        required=True,
        index=True,
    )
    employee_id = fields.Many2one("hr.employee", string="Employe", index=True)
    attendance_id = fields.Many2one(
        "hr.attendance",
        string="Presence generee",
        readonly=True,
        copy=False,
        ondelete="set null",
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

    def _check_zkteco_manager(self):
        if not self.env.user.has_group(
            "portail_rh.group_portail_rh_hr"
        ) and not self.env.user.has_group("base.group_system"):
            raise UserError(_("Seuls les utilisateurs RH peuvent gerer les pointages ZKTeco."))

    @staticmethod
    def _zkteco_get_json(api_url, api_key, endpoint):
        http_request = Request(
            "%s%s" % (api_url.rstrip("/"), endpoint),
            headers={"Accept": "application/json", "X-API-Key": api_key},
        )
        try:
            with urlopen(http_request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, ValueError) as error:
            raise UserError(_("Impossible de joindre le simulateur ZKTeco : %s") % error) from error

    @staticmethod
    def _zkteco_datetime(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    @api.model
    def _zkteco_connection(self):
        return (
            os.getenv("ZKTECO_API_URL", "http://zkteco-mock:8090"),
            os.getenv("ZKTECO_API_KEY", "zkteco-demo-key"),
        )

    @api.model
    def _zkteco_employee_mapping(self, source_employees):
        Employee = self.env["hr.employee"].sudo()
        mapping = {
            employee.zkteco_user_id: employee.id
            for employee in Employee.search([("zkteco_user_id", "!=", False)])
        }
        for source_employee in source_employees:
            device_user_id = source_employee["device_user_id"]
            if device_user_id in mapping:
                continue
            employee = Employee.search(
                [("work_email", "=ilike", source_employee["email"])], limit=1
            )
            if employee:
                if not employee.zkteco_user_id:
                    employee.zkteco_user_id = device_user_id
                mapping[device_user_id] = employee.id
        return mapping

    @api.model
    def _import_zkteco_mock(self):
        api_url, api_key = self._zkteco_connection()
        employees = self._zkteco_get_json(api_url, api_key, "/api/v1/employees")["data"]
        devices = self._zkteco_get_json(api_url, api_key, "/api/v1/devices")["data"]
        employee_by_device_id = self._zkteco_employee_mapping(employees)
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
                Log.create(
                    {
                        "device_user_id": punch["device_user_id"],
                        "employee_id": employee_id,
                        "punch_datetime": self._zkteco_datetime(punch["punch_datetime_utc"]),
                        "punch_type": punch["punch_type"],
                        "device_name": device_names.get(
                            punch["device_serial"], punch["device_serial"]
                        ),
                        "device_serial": punch["device_serial"],
                        "external_uid": punch["external_uid"],
                        "state": "mapped" if employee_id else "error",
                        "error_message": False
                        if employee_id
                        else _("Employe Odoo introuvable."),
                    }
                )
                imported_count += 1
                unmatched_count += not bool(employee_id)
            if not payload["pagination"]["has_more"]:
                break
            after_id = payload["pagination"]["next_after_id"]
        return {
            "imported": imported_count,
            "duplicates": duplicate_count,
            "unmatched": unmatched_count,
        }

    @api.model
    def _map_unmatched_logs(self):
        Log = self.sudo()
        logs = Log.search(
            [
                ("employee_id", "=", False),
                ("attendance_id", "=", False),
                ("state", "in", ("raw", "error")),
            ]
        )
        employees = self.env["hr.employee"].sudo().search(
            [("zkteco_user_id", "in", logs.mapped("device_user_id"))]
        )
        mapping = {employee.zkteco_user_id: employee.id for employee in employees}
        mapped_count = 0
        for log in logs:
            employee_id = mapping.get(log.device_user_id)
            if employee_id:
                log.write(
                    {
                        "employee_id": employee_id,
                        "state": "mapped",
                        "error_message": False,
                    }
                )
                mapped_count += 1
        return mapped_count

    @staticmethod
    def _local_log_date(log):
        punch_datetime = fields.Datetime.to_datetime(log.punch_datetime)
        return pytz.UTC.localize(punch_datetime).astimezone(
            pytz.timezone(log.employee_id._get_tz())
        ).date()

    @api.model
    def _process_mapped_logs(self):
        Log = self.sudo()
        Attendance = self.env["hr.attendance"].sudo()
        logs = Log.search(
            [
                ("state", "in", ("mapped", "error")),
                ("employee_id", "!=", False),
                ("attendance_id", "=", False),
            ],
            order="employee_id, punch_datetime, id",
        )
        grouped_logs = defaultdict(list)
        for log in logs:
            grouped_logs[(log.employee_id.id, self._local_log_date(log))].append(log)

        processed_count = 0
        error_count = 0
        for day_logs in grouped_logs.values():
            pending_check_in = False
            for log in day_logs:
                if log.punch_type == "check_in":
                    if pending_check_in:
                        pending_check_in.write(
                            {
                                "state": "error",
                                "error_message": _("Sortie manquante avant la nouvelle entree."),
                            }
                        )
                        error_count += 1
                    pending_check_in = log
                    continue

                if log.punch_type != "check_out":
                    log.write(
                        {
                            "state": "error",
                            "error_message": _("Type de pointage inconnu."),
                        }
                    )
                    error_count += 1
                    continue

                if not pending_check_in:
                    log.write(
                        {
                            "state": "error",
                            "error_message": _("Entree correspondante introuvable."),
                        }
                    )
                    error_count += 1
                    continue

                try:
                    with self.env.cr.savepoint():
                        attendance = Attendance.create(
                            {
                                "employee_id": log.employee_id.id,
                                "check_in": pending_check_in.punch_datetime,
                                "check_out": log.punch_datetime,
                                "in_mode": "kiosk",
                                "out_mode": "kiosk",
                                "zkteco_managed": True,
                            }
                        )
                except (UserError, ValidationError) as error:
                    message = _("Presence non creee : %s") % error
                    (pending_check_in | log).write(
                        {"state": "error", "error_message": message}
                    )
                    error_count += 2
                else:
                    (pending_check_in | log).write(
                        {
                            "attendance_id": attendance.id,
                            "state": "processed",
                            "error_message": False,
                        }
                    )
                    processed_count += 2
                pending_check_in = False

            if pending_check_in:
                pending_check_in.write(
                    {
                        "state": "error",
                        "error_message": _("Sortie correspondante introuvable."),
                    }
                )
                error_count += 1
        return {"processed": processed_count, "errors": error_count}

    @staticmethod
    def _notification(message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ZKTeco"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_zkteco_mock(self):
        self._check_zkteco_manager()
        result = self._import_zkteco_mock()
        return self._notification(
            _(
                "Import termine : %(imported)s nouveau(x), %(duplicates)s doublon(s), "
                "%(unmatched)s non associe(s)."
            )
            % result
        )

    def action_map_employees(self):
        self._check_zkteco_manager()
        mapped_count = self._map_unmatched_logs()
        return self._notification(
            _("%(count)s log(s) associe(s) a un employe.") % {"count": mapped_count}
        )

    def action_process_logs(self):
        self._check_zkteco_manager()
        result = self._process_mapped_logs()
        return self._notification(
            _("Traitement termine : %(processed)s log(s) traite(s), %(errors)s erreur(s).")
            % result
        )

    def action_sync_and_process(self):
        self._check_zkteco_manager()
        imported = self._import_zkteco_mock()
        mapped_count = self._map_unmatched_logs()
        processed = self._process_mapped_logs()
        values = {**imported, **processed, "mapped": mapped_count}
        return self._notification(
            _(
                "Synchronisation terminee : %(imported)s importe(s), %(duplicates)s doublon(s), "
                "%(mapped)s associe(s), %(processed)s traite(s), %(errors)s erreur(s)."
            )
            % values
        )

    @api.model
    def _cron_sync_zkteco(self):
        self.sudo()._import_zkteco_mock()
        self.sudo()._map_unmatched_logs()
        self.sudo()._process_mapped_logs()
