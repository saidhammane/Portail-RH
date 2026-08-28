from odoo.tests.common import TransactionCase, new_test_user


class PortailRHCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_user = new_test_user(
            cls.env,
            login="portail_rh_employee_test",
            groups="portail_rh.group_portail_rh_employee",
            name="Employe Test",
        )
        cls.other_user = new_test_user(
            cls.env,
            login="portail_rh_other_test",
            groups="portail_rh.group_portail_rh_employee",
            name="Autre Employe Test",
        )
        cls.manager_user = new_test_user(
            cls.env,
            login="portail_rh_manager_test",
            groups="portail_rh.group_portail_rh_manager",
            name="Manager Test",
        )
        cls.hr_user = new_test_user(
            cls.env,
            login="portail_rh_hr_test",
            groups="portail_rh.group_portail_rh_hr",
            name="RH Test",
        )

        cls.department = cls.env["hr.department"].create({"name": "Departement Test"})
        cls.other_department = cls.env["hr.department"].create(
            {"name": "Autre Departement Test"}
        )
        cls.manager_employee = cls.env["hr.employee"].create(
            {
                "name": "Manager Test",
                "user_id": cls.manager_user.id,
                "department_id": cls.department.id,
            }
        )
        cls.department.manager_id = cls.manager_employee
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Employe Test",
                "user_id": cls.employee_user.id,
                "department_id": cls.department.id,
                "parent_id": cls.manager_employee.id,
            }
        )
        cls.other_employee = cls.env["hr.employee"].create(
            {
                "name": "Autre Employe Test",
                "user_id": cls.other_user.id,
                "department_id": cls.other_department.id,
            }
        )

    @classmethod
    def create_travel(cls, employee=None, **values):
        values = {
            "name": "Mission de test",
            "employee_id": (employee or cls.employee).id,
            "destination": "Rabat",
            "date_from": "2026-09-01",
            "date_to": "2026-09-03",
            "estimated_cost": 1200.0,
            **values,
        }
        return cls.env["hr.travel.request"].with_user(cls.employee_user).create(values)

    @classmethod
    def create_supply(cls, employee=None, **values):
        values = {
            "employee_id": (employee or cls.employee).id,
            "item_name": "Ecran",
            "quantity": 1.0,
            "estimated_cost": 2500.0,
            **values,
        }
        return cls.env["hr.supply.request"].with_user(cls.employee_user).create(values)

    @classmethod
    def create_attestation(cls, employee=None, **values):
        values = {
            "employee_id": (employee or cls.employee).id,
            "attestation_type": "work",
            **values,
        }
        return cls.env["hr.attestation.request"].with_user(cls.employee_user).create(values)
