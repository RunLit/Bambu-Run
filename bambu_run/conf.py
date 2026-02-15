"""
App-level settings with sensible defaults.

Override in your Django settings.py:
    BAMBU_RUN_TIMEZONE = 'Australia/Melbourne'
    BAMBU_RUN_BASE_TEMPLATE = 'base/base.html'
"""

from django.conf import settings


def get_setting(name, default):
    return getattr(settings, name, default)


# Timezone for all timestamp display and queries
BAMBU_RUN_TIMEZONE = property(lambda self: get_setting("BAMBU_RUN_TIMEZONE", "UTC"))

# Base template that all bambu_run templates extend
BAMBU_RUN_BASE_TEMPLATE = property(
    lambda self: get_setting("BAMBU_RUN_BASE_TEMPLATE", "bambu_run/base.html")
)

# Login URL for @login_required redirects
BAMBU_RUN_LOGIN_URL = property(
    lambda self: get_setting("BAMBU_RUN_LOGIN_URL", "/accounts/login/")
)

# Default brand for auto-created filaments from MQTT
BAMBU_RUN_AUTO_CREATE_BRAND = property(
    lambda self: get_setting("BAMBU_RUN_AUTO_CREATE_BRAND", "Bambu Lab")
)


class _Settings:
    """Lazy settings object that reads from Django settings with defaults."""

    @property
    def TIMEZONE(self):
        return get_setting("BAMBU_RUN_TIMEZONE", "UTC")

    @property
    def BASE_TEMPLATE(self):
        return get_setting("BAMBU_RUN_BASE_TEMPLATE", "bambu_run/base.html")

    @property
    def LOGIN_URL(self):
        return get_setting("BAMBU_RUN_LOGIN_URL", "/accounts/login/")

    @property
    def AUTO_CREATE_BRAND(self):
        return get_setting("BAMBU_RUN_AUTO_CREATE_BRAND", "Bambu Lab")


app_settings = _Settings()
