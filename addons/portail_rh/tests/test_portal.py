from lxml import html

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestPortailRHHttp(HttpCase):
    password = "Portail-RH-Test-2026"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
