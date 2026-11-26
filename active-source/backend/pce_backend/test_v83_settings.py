import os

from .settings import *  # noqa: F401,F403


_v83_test_database = os.environ.get(
    "PCE_V83_TEST_DATABASE_PATH",
    str(BASE_DIR / "canary-data" / "v83-test.sqlite3"),
)
DATABASES["default"]["NAME"] = _v83_test_database
DATABASES["default"]["TEST"] = {"NAME": _v83_test_database}
TEST_RUNNER = "pce_backend.v83_test_runner.ExistingIsolatedDatabaseRunner"
