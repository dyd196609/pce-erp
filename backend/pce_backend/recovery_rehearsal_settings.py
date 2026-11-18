"""Fail-closed settings for Supplier/Procurement recovery rehearsals."""

import os
from pathlib import Path

from .settings import *  # noqa: F403


_database_text = os.environ.get("PCE_RECOVERY_DATABASE_PATH", "").strip()
_expected_text = os.environ.get("PCE_RECOVERY_EXPECTED_DATABASE_PATH", "").strip()
_run_id = os.environ.get("PCE_RECOVERY_RUN_ID", "").strip()
if not _database_text or not _expected_text or not _run_id:
    raise RuntimeError(
        "Recovery rehearsal requires PCE_RECOVERY_DATABASE_PATH, "
        "PCE_RECOVERY_EXPECTED_DATABASE_PATH and PCE_RECOVERY_RUN_ID"
    )

_database = Path(_database_text).resolve()
_expected = Path(_expected_text).resolve()
_production = (BASE_DIR / "db.sqlite3").resolve()  # noqa: F405
if _database != _expected:
    raise RuntimeError("Recovery database path does not match the expected isolated target")
if _database == _production:
    raise RuntimeError("Production database is forbidden in recovery rehearsal settings")
if "recovery" not in str(_database).casefold() or _database.suffix.casefold() != ".sqlite3":
    raise RuntimeError("Recovery target must be an explicitly named recovery SQLite database")

DATABASES["default"]["NAME"] = str(_database)  # noqa: F405
PCE_RECOVERY_REHEARSAL = True
PCE_RECOVERY_RUN_ID = _run_id
PCE_PRODUCTION_DATABASE_PATH = str(_production)
