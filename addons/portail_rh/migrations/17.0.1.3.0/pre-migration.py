DEPARTMENT_MANAGER_XMLIDS = (
    ("dept_rh", "emp_mgr_rh"),
    ("dept_it", "emp_mgr_it"),
    ("dept_fin", "emp_mgr_fin"),
)


def _backfill_demo_department_managers(cr):
    for department_xmlid, manager_xmlid in DEPARTMENT_MANAGER_XMLIDS:
        cr.execute(
            """
            UPDATE hr_department AS department
               SET manager_id = manager_data.res_id
              FROM ir_model_data AS department_data,
                   ir_model_data AS manager_data
             WHERE department_data.module = 'portail_rh'
               AND department_data.name = %s
               AND department_data.model = 'hr.department'
               AND manager_data.module = 'portail_rh'
               AND manager_data.name = %s
               AND manager_data.model = 'hr.employee'
               AND department.id = department_data.res_id
               AND department.manager_id IS NULL
            """,
            (department_xmlid, manager_xmlid),
        )


def _sync_supply_request_related_fields(cr):
    cr.execute("SELECT to_regclass('hr_supply_request')")
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        UPDATE hr_supply_request AS supply
           SET department_id = employee.department_id
          FROM hr_employee AS employee
         WHERE employee.id = supply.employee_id
           AND supply.department_id IS DISTINCT FROM employee.department_id
        """
    )
    cr.execute(
        """
        UPDATE hr_supply_request AS supply
           SET manager_id = department.manager_id
          FROM hr_department AS department
         WHERE department.id = supply.department_id
           AND supply.manager_id IS DISTINCT FROM department.manager_id
        """
    )


def _replace_indicators_menu_groups(cr):
    cr.execute(
        """
        SELECT menu_data.res_id,
               manager_group.res_id,
               hr_group.res_id
          FROM ir_model_data AS menu_data
          JOIN ir_model_data AS manager_group
            ON manager_group.module = 'portail_rh'
           AND manager_group.name = 'group_portail_rh_manager'
           AND manager_group.model = 'res.groups'
          JOIN ir_model_data AS hr_group
            ON hr_group.module = 'portail_rh'
           AND hr_group.name = 'group_portail_rh_hr'
           AND hr_group.model = 'res.groups'
         WHERE menu_data.module = 'portail_rh'
           AND menu_data.name = 'menu_hr_travel_request_indicators'
           AND menu_data.model = 'ir.ui.menu'
        """
    )
    row = cr.fetchone()
    if not row:
        return

    menu_id, manager_group_id, hr_group_id = row
    cr.execute("DELETE FROM ir_ui_menu_group_rel WHERE menu_id = %s", (menu_id,))
    cr.executemany(
        """
        INSERT INTO ir_ui_menu_group_rel (menu_id, gid)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        [(menu_id, manager_group_id), (menu_id, hr_group_id)],
    )


def migrate(cr, version):
    _backfill_demo_department_managers(cr)
    _sync_supply_request_related_fields(cr)
    _replace_indicators_menu_groups(cr)
