OLD_SEED_XMLIDS = (
    "dept_rh",
    "dept_it",
    "dept_fin",
    "user_mgr_rh",
    "user_mgr_it",
    "user_mgr_fin",
    "emp_mgr_rh",
    "emp_mgr_it",
    "emp_mgr_fin",
    "user_emp_rh_1",
    "user_emp_rh_2",
    "user_emp_it_1",
    "user_emp_it_2",
    "user_emp_fin_1",
    "user_emp_fin_2",
    "emp_rh_1",
    "emp_rh_2",
    "emp_it_1",
    "emp_it_2",
    "emp_fin_1",
    "emp_fin_2",
    "user_mgr_rh_res_partner",
    "user_mgr_it_res_partner",
    "user_mgr_fin_res_partner",
    "user_emp_rh_1_res_partner",
    "user_emp_rh_2_res_partner",
    "user_emp_it_1_res_partner",
    "user_emp_it_2_res_partner",
    "user_emp_fin_1_res_partner",
    "user_emp_fin_2_res_partner",
)


def migrate(cr, version):
    cr.execute("SELECT demo FROM ir_module_module WHERE name = 'portail_rh'")
    row = cr.fetchone()
    module_demo_enabled = bool(row and row[0])
    if module_demo_enabled:
        return

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'portail_rh'
          AND name = ANY(%s)
        """,
        (list(OLD_SEED_XMLIDS),),
    )
