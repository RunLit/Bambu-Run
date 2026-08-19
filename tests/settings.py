"""Minimal Django settings for running bambu_run's pytest suite (in-memory SQLite)."""
import os

# test_mcp_toolkit.py drives real MCP dispatch through `mcp.client.Client`,
# which runs the test body on the asyncio event loop (via pytest-anyio) while
# still using plain synchronous Django ORM calls (Printer.objects.create(),
# and the ORM calls inside the tool functions themselves). Django's asyncio
# safety net treats any sync ORM call made while an event loop is running as
# unsafe by default. It's genuinely safe here: sqlite is in-memory, tests run
# single-threaded, and there's no concurrent request interleaving to corrupt
# a shared connection. Set at settings-import time (before any test body
# runs) rather than per-test, since Django reads this env var at call time.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

SECRET_KEY = "test-secret-key"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "bambu_run",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "tests.urls"
