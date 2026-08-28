from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from .common import PortailRHCase


@tagged("post_install", "-at_install")
class TestAttendanceProcessing(PortailRHCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env["resource.calendar"].create(
            {
                "name": "Calendrier ZKTeco Test",
                "tz": "UTC",
                "attendance_ids": [
                    Command.create(
                        {
                            "name": "Lundi matin",
                            "dayofweek": "0",
                            "day_period": "morning",
                            "hour_from": 8.0,
                            "hour_to": 12.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Lundi apres-midi",
                            "dayofweek": "0",
                            "day_period": "afternoon",
                            "hour_from": 13.0,
                            "hour_to": 17.0,
                        }
                    ),
                ],
            }
        )
        cls.employee.resource_calendar_id = cls.calendar
        cls.employee.zkteco_user_id = "ZK-TEST-001"

    def _create_log(self, punch_datetime, punch_type, external_uid):
        return self.env["hr.attendance.device.log"].create(
            {
                "device_user_id": self.employee.zkteco_user_id,
                "employee_id": self.employee.id,
                "punch_datetime": punch_datetime,
                "punch_type": punch_type,
                "device_serial": "TEST-DEVICE",
                "external_uid": external_uid,
                "state": "mapped",
            }
        )

    def test_process_pair_and_compute_indicators(self):
        check_in = self._create_log("2026-07-06 08:15:00", "check_in", "pair-in")
        check_out = self._create_log("2026-07-06 16:30:00", "check_out", "pair-out")

        with patch.dict("os.environ", {"ZKTECO_TIMEZONE": "UTC"}):
            result = self.env["hr.attendance.device.log"]._process_mapped_logs()

        self.assertEqual(result, {"processed": 2, "errors": 0})
        self.assertEqual(check_in.state, "processed")
        self.assertEqual(check_out.state, "processed")
        self.assertEqual(check_in.attendance_id, check_out.attendance_id)
        self.assertTrue(check_in.attendance_id.zkteco_managed)
        self.assertEqual(check_in.attendance_id.zkteco_late_minutes, 15)
        self.assertEqual(check_in.attendance_id.zkteco_early_departure_minutes, 30)
        self.assertEqual(check_in.attendance_id.zkteco_status, "late_early")

    def test_missing_checkout_is_retried_when_later_log_arrives(self):
        check_in = self._create_log("2026-07-06 08:00:00", "check_in", "retry-in")
        first_result = self.env["hr.attendance.device.log"]._process_mapped_logs()
        self.assertEqual(first_result, {"processed": 0, "errors": 1})
        self.assertEqual(check_in.state, "error")

        check_out = self._create_log("2026-07-06 17:00:00", "check_out", "retry-out")
        second_result = self.env["hr.attendance.device.log"]._process_mapped_logs()
        self.assertEqual(second_result, {"processed": 2, "errors": 0})
        self.assertEqual(check_in.state, "processed")
        self.assertEqual(check_out.state, "processed")
        self.assertEqual(check_in.attendance_id, check_out.attendance_id)
