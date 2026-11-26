"""Hard-guarded SQLite settings for order engineering baseline isolation tests."""

import os
from pathlib import Path

from .settings import *  # noqa: F401,F403


_base = Path(os.environ.get("PCE_ORDER_ENGINEERING_BASELINE_DATABASE_PATH", "")).resolve()
_test = Path(os.environ.get("PCE_ORDER_ENGINEERING_BASELINE_TEST_DATABASE_PATH", "")).resolve()
_production_like = (BASE_DIR / "db.sqlite3").resolve()
for _path in (_base, _test):
    if "pde-order-engineering-baseline-isolated" not in str(_path).lower():
        raise RuntimeError("隔离测试数据库路径必须包含 pde-order-engineering-baseline-isolated")
    if _path == _production_like:
        raise RuntimeError("隔离测试禁止指向开发者数据库 db.sqlite3")

DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"
DATABASES["default"]["NAME"] = str(_base)
DATABASES["default"]["TEST"] = {"NAME": str(_test)}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
