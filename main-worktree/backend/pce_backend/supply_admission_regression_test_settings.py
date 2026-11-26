"""Empty in-memory regression schema; migration is separately tested on a clone."""
from .test_settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIGRATION_MODULES = {name: None for name in INSTALLED_APPS if not name.startswith("django.")}
