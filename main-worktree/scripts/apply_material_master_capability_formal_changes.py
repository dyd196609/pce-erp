"""Controlled formal write for the approved Material Master capability facts.

This is not a seed or migration.  It invokes the single formal master-data
service with the user-confirmed category identity and the audited UOM relation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_ACTOR = "emd_emp047"
EXPECTED_COMPANY = "COMP001"
CATEGORY_CODE = "MATCAT-SOLID-WOOD"
CATEGORY_NAME = "\u5b9e\u6728"
CATEGORY_IDEMPOTENCY_KEY = (
    "MM-CAPABILITY-20261006:CATEGORY:MATCAT-SOLID-WOOD:V1"
)
UOM_IDEMPOTENCY_KEY = "MM-CAPABILITY-20261006:UOM:COMP001:MM-TO-M:V1"


def configure(database: Path) -> None:
    if database.resolve() != EXPECTED_DATABASE or not database.is_file():
        raise RuntimeError("FORMAL_DATABASE_TARGET_MISMATCH")
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database.resolve())
    os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
    os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
    os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    if args.actor != EXPECTED_ACTOR:
        raise RuntimeError("FORMAL_ACTOR_MISMATCH")
    configure(database)

    from django.conf import settings
    from django.db import transaction
    from masterdata.material_identity import normalize_identity_text
    from masterdata.models import MaterialCategory, UnitOfMeasure
    from pde.production_foundation_service import ProductionFoundationService
    from system.models import Company, User

    if Path(settings.DATABASES["default"]["NAME"]).resolve() != EXPECTED_DATABASE:
        raise RuntimeError("DJANGO_DATABASE_TARGET_MISMATCH")
    company = Company.objects.get(code=EXPECTED_COMPANY, is_active=True)
    actor = User.objects.get(
        username=EXPECTED_ACTOR, is_active=True, company_id=company.pk,
    )
    if actor.is_superuser:
        raise RuntimeError("SUPERUSER_ACTOR_FORBIDDEN")

    same_code = list(MaterialCategory.objects.filter(code__iexact=CATEGORY_CODE))
    conflicting_code = [
        row for row in same_code
        if row.company_id != company.pk
        or normalize_identity_text(row.name) != normalize_identity_text(CATEGORY_NAME)
    ]
    if conflicting_code:
        raise RuntimeError("MATERIAL_CATEGORY_CODE_CONFLICT")
    same_name = [
        row for row in MaterialCategory.objects.filter(
            company_id=company.pk, is_active=True,
        )
        if normalize_identity_text(row.name) == normalize_identity_text(CATEGORY_NAME)
    ]
    if any(row.code.casefold() != CATEGORY_CODE.casefold() for row in same_name):
        raise RuntimeError("ACTIVE_MATERIAL_CATEGORY_SYNONYM_CONFLICT")

    millimeter = UnitOfMeasure.objects.get(pk=15)
    meter = UnitOfMeasure.objects.get(pk=17)
    if (
        millimeter.code.casefold() != "mm"
        or meter.code.casefold() != "m"
        or millimeter.company_id != company.pk
        or meter.company_id != company.pk
        or millimeter.dimension != "length"
        or meter.dimension != "length"
        or not millimeter.is_active
        or not meter.is_active
    ):
        raise RuntimeError("FORMAL_UOM_IDENTITY_MISMATCH")

    preflight = {
        "database": str(database),
        "company": {"id": company.pk, "code": company.code},
        "actor": {
            "id": actor.pk, "username": actor.username,
            "isSuperuser": actor.is_superuser,
        },
        "categoryConflictCount": len(conflicting_code),
        "activeSameNameCount": len(same_name),
        "uomBefore": {
            "id": millimeter.pk,
            "code": millimeter.code,
            "conversionBaseId": millimeter.conversion_base_id,
            "conversionFactor": str(millimeter.conversion_factor),
        },
    }
    if not args.apply:
        print(json.dumps({"apply": False, "preflight": preflight}, indent=2))
        return

    with transaction.atomic():
        category_result = ProductionFoundationService.write(
            "material-categories",
            user=actor,
            payload={
                "company_id": company.pk,
                "code": CATEGORY_CODE,
                "name": CATEGORY_NAME,
                "is_active": True,
                "reason": "用户正式裁决建立通用实木物料类别。",
            },
            idempotency_key=CATEGORY_IDEMPOTENCY_KEY,
            source_identity={
                "sourceSystem": "PCE",
                "sourceType": "USER_CONFIRMED_BUSINESS_DECISION",
                "sourceObjectType": "MATERIAL_CATEGORY",
                "externalId": f"{EXPECTED_COMPANY}:{CATEGORY_CODE}",
                "auditMetadata": {
                    "instruction": "MaterialCategory正式编码业务裁决",
                    "scope": "generic-material-category",
                },
            },
        )
        uom_result = ProductionFoundationService.write(
            "units",
            user=actor,
            object_id=millimeter.pk,
            payload={
                "conversion_base_id": meter.pk,
                "conversion_factor": "0.001",
                "reason": "建立正式长度单位关系：1 mm = 0.001 m。",
            },
            idempotency_key=UOM_IDEMPOTENCY_KEY,
            source_identity=None,
        )
    print(json.dumps({
        "apply": True,
        "preflight": preflight,
        "category": category_result,
        "uom": uom_result,
    }, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()
