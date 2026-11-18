import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403

DATABASE_OVERRIDE_VARIABLE_NAME = "PCE_DATABASE_PATH"
override_value = os.environ.get(DATABASE_OVERRIDE_VARIABLE_NAME, "").strip()
expected_value = os.environ.get("PCE_V45_EXPECTED_TEST_DATABASE_PATH", "").strip()
if not override_value or not expected_value:
    raise ImproperlyConfigured(
        "V45 database isolation requires PCE_DATABASE_PATH and "
        "PCE_V45_EXPECTED_TEST_DATABASE_PATH"
    )

resolved_database_path = Path(override_value).resolve()
expected_database_path = Path(expected_value).resolve()
default_development_database_path = (BASE_DIR / "db.sqlite3").resolve()
if resolved_database_path != expected_database_path:
    raise ImproperlyConfigured("V45 database override does not match expected path")
if resolved_database_path == default_development_database_path:
    raise ImproperlyConfigured("V45 database must not use backend/db.sqlite3")
if not resolved_database_path.exists():
    raise ImproperlyConfigured("V45 isolated database path must exist before Django starts")

DATABASES["default"]["NAME"] = str(resolved_database_path)
DATABASES["default"]["TEST"] = {
    "NAME": str(resolved_database_path.with_name(
        f"{resolved_database_path.stem}-tests{resolved_database_path.suffix}"
    ))
}
ROOT_URLCONF = "pce_backend.v45_test_urls"
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django.contrib.admin"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MIGRATION_MODULES = {
    "masterdata": None,
    "procurement": None,
    "purchase": None,
    "pfm": None,
}

