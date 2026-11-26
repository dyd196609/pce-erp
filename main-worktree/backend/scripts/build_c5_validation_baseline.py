"""Build the deterministic, non-production C5 validation database baseline.

The baseline is intentionally smaller than an application database.  It owns
only the schema and root organization fact required by the existing
``verify:pce-formal-import-real-session-actor`` gate.  The gate creates its
temporary users, employee, position, responsibility, role, permissions, audit
rows, customer and idempotency facts in an isolated copy.

This builder does not run Django migrations and never reads another database.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys


BASELINE_ID = "PCE-C5-REAL-SESSION-ACTOR-BASELINE-V1"
ROOT_COMPANY = {
    "id": 1,
    "name": "C5隔离验证企业",
    "code": "COMP001",
    "address": "",
    "contact": "",
    "phone": "",
    "is_active": True,
}


def parse_args() -> argparse.Namespace:
    backend_root = Path(__file__).resolve().parents[1]
    default_output = backend_root / "validation" / "c5" / "c5-validation-baseline.sqlite3"
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output)
    return parser.parse_args()


def configure_django(database_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    os.environ["DJANGO_SETTINGS_MODULE"] = "pce_backend.settings"
    os.environ["PCE_DATABASE_PATH"] = str(database_path)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def schema_models():
    from django.contrib.auth.models import Group, Permission as DjangoPermission
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.sessions.models import Session
    from masterdata.models import (
        CodeRule,
        ExternalIdentity,
        MasterDataWriteRequest,
        UnitOfMeasure,
    )
    from pde.models import (
        BOMItem,
        BOMItemSubstitute,
        EngineeringBreakdownItem,
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringRuleDefinition,
        EngineeringSourceRecord,
        Equipment,
        OrderEngineeringInstance,
        ProductCategory,
        RoutingStep,
        StandardCapacity,
        WorkCenter,
    )
    from pfm.models import Employee
    from procurement.models import InventoryLot, WarehouseLocation
    from sales.models import Customer
    from system.models import (
        Company,
        Department,
        OrganizationOperatingAuditRecord,
        OrganizationUnit,
        JobFamily,
        JobLevel,
        Permission,
        Position,
        PositionResponsibility,
        Process,
        Responsibility,
        Role,
        RolePermission,
        Team,
        User,
        UserRoleScopeAssignment,
        Workshop,
    )

    # Dependency order is fixed so the SQLite bytes are reproducible.
    return (
        ContentType,
        DjangoPermission,
        Group,
        Session,
        Company,
        OrganizationUnit,
        Department,
        Workshop,
        Team,
        Process,
        JobFamily,
        JobLevel,
        Role,
        Permission,
        Responsibility,
        Position,
        User,
        Employee,
        RolePermission,
        PositionResponsibility,
        UserRoleScopeAssignment,
        OrganizationOperatingAuditRecord,
        Customer,
        ExternalIdentity,
        MasterDataWriteRequest,
        UnitOfMeasure,
        CodeRule,
        ProductCategory,
        WorkCenter,
        Equipment,
        StandardCapacity,
        EngineeringSourceRecord,
        EngineeringRuleDefinition,
        OrderEngineeringInstance,
        EngineeringCalculationRecord,
        EngineeringBreakdownItem,
        EngineeringCalculationDetail,
        EngineeringDerivedFact,
        BOMItem,
        BOMItemSubstitute,
        RoutingStep,
        WarehouseLocation,
        InventoryLot,
    )


def create_baseline(output: Path) -> dict:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    configure_django(output)
    import django

    django.setup()
    from django.db import connection
    from system.models import Company

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA page_size=4096")
        cursor.execute("PRAGMA auto_vacuum=NONE")
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=FULL")

    models = schema_models()
    with connection.schema_editor() as editor:
        for model in models:
            editor.create_model(model)

    Company.objects.create(**ROOT_COMPANY)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA user_version=1")
        cursor.execute("VACUUM")
    connection.close()

    payload = output.read_bytes()
    with sqlite3.connect(f"file:{output}?mode=ro", uri=True) as database:
        tables = [
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        counts = {
            table: database.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
            if table != "sqlite_sequence"
        }

    return {
        "baselineId": BASELINE_ID,
        "path": str(output),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "tableCountIncludingInternal": len(tables),
        "tables": tables,
        "nonZeroFacts": {table: count for table, count in counts.items() if count},
        "rootCompany": ROOT_COMPANY,
        "productionBusinessFacts": 0,
        "migrationUsed": False,
    }


def main() -> None:
    args = parse_args()
    print(json.dumps(create_baseline(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
