"""Only a pre-migrated disposable acceptance clone can run this test suite."""
import os
from pathlib import Path

from django.test.runner import DiscoverRunner
from .settings import *  # noqa: F401,F403

_clone = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if "test-results" not in {part.lower() for part in _clone.parts} or "order-line-supply-admission-isolated" not in _clone.name or not _clone.exists():
    raise RuntimeError("供应确认测试仅允许预先迁移的test-results隔离副本。")
DATABASES["default"]["NAME"] = str(_clone)
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


class IsolatedCloneRunner(DiscoverRunner):
    # TestCase itself encloses fixtures and every test in rollback transactions.
    # Avoid migrating/flushing unrelated histories in the copied acceptance DB.
    def setup_databases(self, **kwargs):
        return None

    def teardown_databases(self, old_config, **kwargs):
        pass


TEST_RUNNER = "pce_backend.order_line_supply_admission_test_settings.IsolatedCloneRunner"
