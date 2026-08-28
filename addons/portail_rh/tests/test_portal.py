import base64
import uuid
from unittest.mock import patch

from lxml import html

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestPortailRHHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.password = "test-" + uuid.uuid4().hex
        cls.portal_user = new_test_user(
            cls.env,
            login="portail_rh_http_employee",
            password=cls.password,
            groups="portail_rh.group_portail_rh_employee",
            name="Employe Portail HTTP",
        )
        cls.other_user = new_test_user(
            cls.env,
            login="portail_rh_http_other",
            password=cls.password,
            groups="portail_rh.group_portail_rh_employee",
            name="Autre Employe Portail HTTP",
        )
        cls.hr_user = new_test_user(
            cls.env,
            login="portail_rh_http_hr",
            groups="portail_rh.group_portail_rh_hr",
            name="RH Portail HTTP",
        )
        cls.department = cls.env["hr.department"].create({"name": "Portail HTTP"})
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Employe Portail HTTP",
                "user_id": cls.portal_user.id,
                "department_id": cls.department.id,
            }
        )
        cls.other_employee = cls.env["hr.employee"].create(
            {
                "name": "Autre Employe Portail HTTP",
                "user_id": cls.other_user.id,
                "department_id": cls.department.id,
            }
        )
        cls.approved_attestation = (
            cls.env["hr.attestation.request"]
            .with_user(cls.portal_user)
            .create(
                {
                    "employee_id": cls.employee.id,
                    "attestation_type": "work",
                    "reason": "Test PDF",
                }
            )
        )
        cls.approved_attestation.with_user(cls.portal_user).action_submit()
        cls.approved_attestation.with_user(cls.hr_user).action_approve()
        cls.onboarding_plan = cls.env["hr.onboarding.plan"].with_user(cls.hr_user).create(
            {
                "name": "Plan portail HTTP",
                "department_id": cls.department.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Lire le guide d'accueil",
                            "description": "Prendre connaissance des procedures.",
                        },
                    )
                ],
            }
        )
        cls.onboarding_document = (
            cls.env["hr.onboarding.document"]
            .with_context(onboarding_skip_enqueue=True)
            .with_user(cls.hr_user)
            .create(
                {
                    "name": "Guide portail HTTP",
                    "file_name": "guide-http.txt",
                    "file_data": base64.b64encode(b"Les horaires sont de 09:00 a 18:00."),
                    "company_id": cls.env.company.id,
                    "visibility": "employee",
                }
            )
        )
        cls.onboarding_document.with_context(onboarding_internal=True).write(
            {"indexing_state": "indexed"}
        )

    def setUp(self):
        super().setUp()
        self.authenticate(self.portal_user.login, self.password)

    @staticmethod
    def _csrf_token(response):
        document = html.fromstring(response.content)
        return document.xpath("//input[@name='csrf_token']/@value")[0]

    def test_portal_lists_and_forms_render(self):
        expected_pages = {
            "/my/travel_requests": "Mes deplacements",
            "/my/travel_requests/new": "Nouvelle demande de deplacement",
            "/my/supply_requests": "Mes fournitures",
            "/my/supply_requests/new": "Nouvelle demande de fournitures",
            "/my/attestation_requests": "Mes attestations",
            "/my/attestation_requests/new": "Nouvelle demande d'attestation",
            "/my/onboarding": "Assistant d'integration",
            "/my/onboarding/checklist": "Ma checklist d'integration",
        }
        for url, expected_text in expected_pages.items():
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(expected_text, response.text, url)

    def test_portal_creates_and_submits_travel_request(self):
        form_response = self.url_open("/my/travel_requests/new")
        create_response = self.url_open(
            "/my/travel_requests/create",
            data={
                "csrf_token": self._csrf_token(form_response),
                "destination": "Casablanca",
                "date_from": "2026-10-05",
                "date_to": "2026-10-06",
                "purpose": "Recette portail",
                "estimated_cost": "850",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertIn("message=created", create_response.url)
        travel = self.env["hr.travel.request"].search(
            [
                ("employee_id", "=", self.employee.id),
                ("destination", "=", "Casablanca"),
            ],
            limit=1,
        )
        self.assertTrue(travel)
        self.assertEqual(travel.state, "draft")

        detail_response = self.url_open("/my/travel_requests/%s" % travel.id)
        submit_response = self.url_open(
            "/my/travel_requests/%s/submit" % travel.id,
            data={"csrf_token": self._csrf_token(detail_response)},
        )
        self.assertEqual(submit_response.status_code, 200)
        self.assertIn("message=submitted", submit_response.url)
        self.assertEqual(travel.state, "submitted")

    def test_portal_hides_other_employee_records(self):
        other_request = (
            self.env["hr.attestation.request"]
            .with_user(self.other_user)
            .create(
                {
                    "employee_id": self.other_employee.id,
                    "attestation_type": "salary",
                }
            )
        )
        response = self.url_open("/my/attestation_requests/%s" % other_request.id)
        self.assertEqual(response.status_code, 404)

    def test_approved_attestation_pdf_download(self):
        response = self.url_open(
            "/my/attestation_requests/%s/pdf" % self.approved_attestation.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
        self.assertTrue(
            response.content.startswith((b"%PDF", b"<!DOCTYPE html>")),
            "Unexpected report prefix: %r" % response.content[:120],
        )

    def test_onboarding_chat_citations_feedback_and_checklist(self):
        page = self.url_open("/my/onboarding")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Lire le guide d&#39;accueil", page.text)
        ai_response = {
            "answer": "Les horaires sont de 09:00 a 18:00 [1].",
            "sources": [
                {
                    "document_id": self.onboarding_document.id,
                    "title": "Titre non fiable",
                    "section": "Chunk 1",
                    "score": 0.88,
                }
            ],
            "confidence": 0.88,
            "latency_ms": 25,
            "cache_hit": False,
            "needs_escalation": False,
        }
        with patch(
            "odoo.addons.portail_rh.controllers.portal.PortailRHPortal._call_onboarding_ai",
            return_value=ai_response,
        ):
            response = self.url_open(
                "/my/onboarding/ask",
                data={
                    "csrf_token": self._csrf_token(page),
                    "question": "Quels sont mes horaires ?",
                },
            )
        self.assertEqual(response.status_code, 200)
        assistant = self.env["hr.onboarding.message"].sudo().search(
            [
                ("conversation_id.user_id", "=", self.portal_user.id),
                ("role", "=", "assistant"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertEqual(assistant.source_document_ids, self.onboarding_document)
        self.assertIn("[1]", assistant.content)
        self.assertIn("Guide portail HTTP", response.text)

        feedback_response = self.url_open(
            "/my/onboarding/feedback",
            data={
                "csrf_token": self._csrf_token(response),
                "message_id": str(assistant.id),
                "feedback": "helpful",
            },
        )
        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(assistant.feedback, "helpful")

    def test_onboarding_rechecks_sources_and_escalates_unknown_question(self):
        restricted_document = (
            self.env["hr.onboarding.document"]
            .with_context(onboarding_skip_enqueue=True)
            .with_user(self.hr_user)
            .create(
                {
                    "name": "Document RH interdit",
                    "file_name": "rh-interdit.txt",
                    "file_data": base64.b64encode(b"Information confidentielle."),
                    "company_id": self.env.company.id,
                    "visibility": "hr",
                }
            )
        )
        restricted_document.with_context(onboarding_internal=True).write(
            {"indexing_state": "indexed"}
        )
        page = self.url_open("/my/onboarding")
        unsafe_response = {
            "answer": "Information confidentielle [1].",
            "sources": [
                {
                    "document_id": restricted_document.id,
                    "title": restricted_document.name,
                    "section": "Chunk 1",
                    "score": 0.99,
                }
            ],
            "confidence": 0.99,
            "latency_ms": 10,
            "cache_hit": False,
            "needs_escalation": False,
        }
        with patch(
            "odoo.addons.portail_rh.controllers.portal.PortailRHPortal._call_onboarding_ai",
            return_value=unsafe_response,
        ):
            response = self.url_open(
                "/my/onboarding/ask",
                data={
                    "csrf_token": self._csrf_token(page),
                    "question": "Donnez-moi le document RH.",
                },
            )
        assistant = self.env["hr.onboarding.message"].sudo().search(
            [
                ("conversation_id.user_id", "=", self.portal_user.id),
                ("role", "=", "assistant"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertFalse(assistant.source_document_ids)
        self.assertTrue(assistant.needs_escalation)
        self.assertIn("Information insuffisante", assistant.content)

        escalation_response = self.url_open(
            "/my/onboarding/escalate",
            data={
                "csrf_token": self._csrf_token(response),
                "message_id": str(assistant.id),
            },
        )
        self.assertEqual(escalation_response.status_code, 200)
        self.assertTrue(assistant.escalation_activity_id)
        self.assertEqual(assistant.escalation_activity_id.res_id, self.employee.id)
