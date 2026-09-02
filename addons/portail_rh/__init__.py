import os

from . import models
from . import controllers


def post_init_hook(env):
    """Optionally install the complete Bravico demo without storing a password."""
    demo_password = os.getenv("PORTAIL_RH_DEMO_PASSWORD")
    if not demo_password:
        return
    env["portail_rh.company.demo"].seed(demo_password)
