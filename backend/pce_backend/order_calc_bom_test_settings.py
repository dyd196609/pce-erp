"""Hard-guarded SQLite settings for the PDE order calculation/BOM closure tests."""

import os
from pathlib import Path

from .settings import *  # noqa: F401,F403


_base = Path(os.environ.get("PCE_ORDER_CALC_BOM_DATABASE_PATH", "")).resolve()
_test = Path(os.environ.get("PCE_ORDER_CALC_BOM_TEST_DATABASE_PATH", "")).resolve()
_production_like = (BASE_DIR / "db.sqlite3").resolve()
for _path in (_base, _test):
    if "pde-order-calc-bom-isolated" not in str(_path).lower():
        raise RuntimeError("隔离测试数据库路径必须包含 pde-order-calc-bom-isolated")
    if _path == _production_like:
        raise RuntimeError("隔离测试禁止指向开发者数据库 db.sqlite3")

DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"
DATABASES["default"]["NAME"] = str(_base)
DATABASES["default"]["TEST"] = {"NAME": str(_test)}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
