"""WSGI config for Bambu Run standalone deployment."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "standalone.settings")

application = get_wsgi_application()

# Read-only deployments (SESSION_ENGINE=signed_cookies) point at a database
# whose user has no write access. Django writes to auth_user.last_login on
# every successful login by default, which would error out against such a
# user and break login entirely — so skip that write here.
from django.conf import settings  # noqa: E402

if settings.SESSION_ENGINE == "django.contrib.sessions.backends.signed_cookies":
    from django.contrib.auth.models import update_last_login
    from django.contrib.auth.signals import user_logged_in

    user_logged_in.disconnect(update_last_login, dispatch_uid="update_last_login")
