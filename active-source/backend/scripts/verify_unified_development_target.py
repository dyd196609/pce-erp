"""Fail-closed, read-only preflight for the single 5173/8075 chain."""

from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import sys
from pathlib import Path


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_PROFILE = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
EXPECTED_DATABASE_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
REQUIRED_TABLES = {
    "user_system",
    "system_company",
    "system_organization_operating_audits",
    "pde_order_cross_functional_review",
    "pde_order_cross_functional_review_item",
    "pde_order_review_participant_grant",
    "pde_product_design_item",
}
REQUIRED_MIGRATIONS = {
    ("pde", "0027_order_review_participant_grant"),
    ("pde", "0028_product_design_plan_content_completion"),
}


def fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    raise SystemExit(2)


def verify_database(configured: Path) -> dict:
    """Verify only stable technical facts; employee and business rows may change normally."""
    if not configured.is_file():
        fail("统一非生产验收库不存在。")
    connection = sqlite3.connect(f"file:{configured.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA quick_check(1)").fetchone()
        if not integrity or integrity[0] != "ok":
            fail("目标库只读完整性检查未通过；禁止启动或切换备用库。")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            fail(f"目标库缺少必需结构：{', '.join(missing)}；禁止迁移或回退到默认库。")
        applied_migrations = {
            (row[0], row[1])
            for row in connection.execute("SELECT app, name FROM django_migrations")
        }
        missing_migrations = sorted(REQUIRED_MIGRATIONS - applied_migrations)
        if missing_migrations:
            labels = ", ".join(f"{app}.{name}" for app, name in missing_migrations)
            fail(f"目标库缺少必需迁移版本：{labels}；禁止启动、迁移或改用其他库。")
        return {
            "databaseOpenMode": "read-only",
            "integrityCheck": integrity[0],
            "requiredTableCount": len(REQUIRED_TABLES),
            "requiredMigrationCount": len(REQUIRED_MIGRATIONS),
        }
    finally:
        connection.close()


def main() -> None:
    if os.environ.get("PCE_RUNTIME_PROFILE", "").strip() != EXPECTED_PROFILE:
        fail(f"PCE_RUNTIME_PROFILE 必须精确声明为：{EXPECTED_PROFILE}")
    if os.environ.get("PCE_DATABASE_IDENTITY", "").strip() != EXPECTED_DATABASE_IDENTITY:
        fail(f"PCE_DATABASE_IDENTITY 必须精确声明为：{EXPECTED_DATABASE_IDENTITY}")
    if os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") != "1":
        fail("PCE_NON_PRODUCTION_ACCEPTANCE 必须精确声明为 1。")

    configured = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
    if configured != EXPECTED_DATABASE:
        fail(f"PCE_DATABASE_PATH 必须精确指向统一非生产验收库：{EXPECTED_DATABASE}")
    technical_facts = verify_database(configured)
    database_sha256 = hashlib.sha256(configured.read_bytes()).hexdigest()
    print(json.dumps({
        "ok": True,
        "profile": EXPECTED_PROFILE,
        "databaseIdentity": EXPECTED_DATABASE_IDENTITY,
        "nonProductionAcceptance": True,
        "database": str(configured),
        "databaseSha256": database_sha256,
        "schemaContract": "PCE-UNIFIED-READ-SCHEMA-V2",
        **technical_facts,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
