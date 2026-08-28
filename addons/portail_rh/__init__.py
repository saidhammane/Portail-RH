import os

from . import models
from . import controllers


def post_init_hook(env):
    """Optionally set local demo passwords without storing one in Git."""
    demo_password = os.getenv("PORTAIL_RH_DEMO_PASSWORD")
    if not demo_password:
        return
    for xml_id in (
        "user_mgr_rh",
        "user_mgr_it",
        "user_mgr_fin",
        "user_emp_rh_1",
        "user_emp_rh_2",
        "user_emp_it_1",
        "user_emp_it_2",
        "user_emp_fin_1",
        "user_emp_fin_2",
    ):
        user = env.ref("portail_rh.%s" % xml_id, raise_if_not_found=False)
        if user:
            user.password = demo_password
