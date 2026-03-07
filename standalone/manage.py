#!/usr/bin/env python
"""Django's command-line utility for Bambu Run standalone deployment."""
import os
import sys

# Ensure the project root (/app) is on sys.path so that both 'standalone'
# and 'bambu_run' are importable regardless of where this script is invoked from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env so manage.py commands pick up env vars outside of systemd/Docker
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "standalone.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
