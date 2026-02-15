"""WSGI config for Bambu Run standalone deployment."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "standalone.settings")

application = get_wsgi_application()
