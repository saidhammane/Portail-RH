import base64
import hashlib

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import PortailRHCase


@tagged("post_install", "-at_install")
class TestOnboardingModels(PortailRHCase):
    def test_only_hr_can_manage_documents(self):
        document = self.env["hr.onboarding.document"].with_user(self.hr_user).create(
            {
                "name": "Guide d'accueil",
                "file_name": "guide.txt",
                "file_data": base64.b64encode(b"Bienvenue dans l'entreprise."),
                "category": "welcome",
                "company_id": self.env.company.id,
                "visibility": "employee",
            }
        )
        self.assertTrue(document.attachment_id)
        self.assertEqual(document.indexing_state, "pending")
        self.assertEqual(
            document.checksum,
            hashlib.sha256(b"Bienvenue dans l'entreprise.").hexdigest(),
        )
        self.assertEqual(document._index_payload()["visibility"], "employee")
        with self.assertRaises(AccessError):
            self.env["hr.onboarding.document"].with_user(self.employee_user).search(
                [("id", "=", document.id)]
            )
        with self.assertRaises(ValidationError):
            self.env["hr.onboarding.document"].with_user(self.hr_user).create(
                {
                    "name": "Archive interdite",
                    "file_name": "archive.zip",
                    "file_data": base64.b64encode(b"not supported"),
                    "company_id": self.env.company.id,
                }
            )

    def test_conversations_are_owned_and_isolated(self):
        conversation = self.env["hr.onboarding.conversation"].with_user(
            self.employee_user
        ).create({"employee_id": self.other_employee.id})
        self.assertEqual(conversation.user_id, self.employee_user)
        self.assertEqual(conversation.employee_id, self.employee)

        other_conversation = self.env["hr.onboarding.conversation"].with_user(
            self.other_user
        ).create({})
        self.env["hr.onboarding.message"].sudo().create(
            {
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": "Reponse avec source.",
                "confidence_score": 0.8,
            }
        )
        employee_conversations = self.env["hr.onboarding.conversation"].with_user(
            self.employee_user
        ).search([("id", "in", (conversation.id, other_conversation.id))])
        self.assertEqual(employee_conversations, conversation)
        with self.assertRaises(AccessError):
            other_conversation.with_user(self.employee_user).read(["started_at"])

    def test_employee_and_manager_checklist_permissions(self):
        plan = self.env["hr.onboarding.plan"].with_user(self.hr_user).create(
            {
                "name": "Integration equipe",
                "department_id": self.department.id,
                "line_ids": [
                    (0, 0, {"name": "Lire le reglement", "sequence": 10}),
                ],
            }
        )
        other_plan = self.env["hr.onboarding.plan"].with_user(self.hr_user).create(
            {
                "name": "Autre equipe",
                "department_id": self.other_department.id,
                "line_ids": [(0, 0, {"name": "Autre tache"})],
            }
        )
        task = self.env["hr.onboarding.employee.task"].with_user(self.hr_user).create(
            {"employee_id": self.employee.id, "plan_line_id": plan.line_ids.id}
        )
        other_task = self.env["hr.onboarding.employee.task"].with_user(
            self.hr_user
        ).create(
            {
                "employee_id": self.other_employee.id,
                "plan_line_id": other_plan.line_ids.id,
            }
        )

        employee_tasks = self.env["hr.onboarding.employee.task"].with_user(
            self.employee_user
        ).search([("id", "in", (task.id, other_task.id))])
        manager_tasks = self.env["hr.onboarding.employee.task"].with_user(
            self.manager_user
        ).search([("id", "in", (task.id, other_task.id))])
        hr_tasks = self.env["hr.onboarding.employee.task"].with_user(self.hr_user).search(
            [("id", "in", (task.id, other_task.id))]
        )
        self.assertEqual(employee_tasks, task)
        self.assertEqual(manager_tasks, task)
        self.assertEqual(hr_tasks, task | other_task)

        task.with_user(self.employee_user).write({"state": "done"})
        self.assertTrue(task.completed_at)
        with self.assertRaises(AccessError):
            task.with_user(self.manager_user).write({"state": "todo"})

        employee_plans = self.env["hr.onboarding.plan"].with_user(
            self.employee_user
        ).search([("id", "in", (plan.id, other_plan.id))])
        self.assertEqual(employee_plans, plan)
