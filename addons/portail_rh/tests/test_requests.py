from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import PortailRHCase


@tagged("post_install", "-at_install")
class TestRequestWorkflows(PortailRHCase):
    def test_employee_cannot_bypass_workflows(self):
        travel = self.create_travel(state="approved")
        supply = self.create_supply(state="done")
        attestation = self.create_attestation(state="approved")

        self.assertEqual(travel.state, "draft")
        self.assertEqual(supply.state, "draft")
        self.assertEqual(attestation.state, "draft")
        for request_record in (travel, supply, attestation):
            with self.assertRaises(UserError):
                request_record.with_user(self.employee_user).write({"state": "approved"})

    def test_travel_workflow_and_manager_activity(self):
        travel = self.create_travel()
        travel.with_user(self.employee_user).action_submit()
        self.assertEqual(travel.state, "submitted")

        activity = self.env["mail.activity"].search(
            [
                ("res_model", "=", travel._name),
                ("res_id", "=", travel.id),
                ("user_id", "=", self.manager_user.id),
            ]
        )
        self.assertTrue(activity)
        with self.assertRaises(UserError):
            travel.with_user(self.employee_user).write({"destination": "Casablanca"})

        travel.with_user(self.manager_user).action_approve()
        self.assertEqual(travel.state, "approved")
        self.assertFalse(activity.exists())
        travel.with_user(self.manager_user).action_done()
        self.assertEqual(travel.state, "done")

    def test_supply_workflow_and_constraints(self):
        supply = self.create_supply()
        supply.with_user(self.employee_user).action_submit()
        supply.with_user(self.manager_user).action_reject()
        self.assertEqual(supply.state, "rejected")
        supply.with_user(self.employee_user).action_set_draft()
        self.assertEqual(supply.state, "draft")

        with self.assertRaises(ValidationError):
            self.create_supply(quantity=0)
        with self.assertRaises(ValidationError):
            self.create_supply(estimated_cost=-1)

    def test_attestation_approval_and_print_access(self):
        attestation = self.create_attestation()
        attestation.with_user(self.employee_user).action_submit()
        with self.assertRaises(UserError):
            attestation.with_user(self.employee_user).action_approve()

        attestation.with_user(self.hr_user).action_approve()
        report_action = attestation.with_user(self.employee_user).action_print_attestation()
        self.assertEqual(report_action["report_type"], "qweb-pdf")

        with self.assertRaises(AccessError):
            attestation.with_user(self.other_user).action_print_attestation()

    def test_record_rules_isolate_employees_and_expose_manager_team(self):
        own_travel = self.create_travel()
        other_travel = self.env["hr.travel.request"].with_user(self.other_user).create(
            {
                "name": "Autre mission",
                "employee_id": self.other_employee.id,
                "destination": "Tanger",
                "date_from": "2026-09-01",
                "date_to": "2026-09-01",
            }
        )

        employee_records = self.env["hr.travel.request"].with_user(self.employee_user).search(
            [("id", "in", (own_travel.id, other_travel.id))]
        )
        manager_records = self.env["hr.travel.request"].with_user(self.manager_user).search(
            [("id", "in", (own_travel.id, other_travel.id))]
        )
        hr_records = self.env["hr.travel.request"].with_user(self.hr_user).search(
            [("id", "in", (own_travel.id, other_travel.id))]
        )
        self.assertEqual(employee_records, own_travel)
        self.assertEqual(manager_records, own_travel)
        self.assertEqual(hr_records, own_travel | other_travel)

    def test_travel_date_constraint_and_duration(self):
        travel = self.create_travel()
        self.assertEqual(travel.duration_days, 3)
        with self.assertRaises(ValidationError):
            self.create_travel(date_from="2026-09-03", date_to="2026-09-01")
