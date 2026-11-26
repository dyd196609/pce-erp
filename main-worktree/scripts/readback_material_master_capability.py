"""Read-only final evidence for the Material Master minimum capability task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import site
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
CATEGORY_CODE = "MATCAT-SOLID-WOOD"
CATEGORY_NAME = "实木"
IDEMPOTENCY_KEYS = (
    "MM-CAPABILITY-20261006:CATEGORY:MATCAT-SOLID-WOOD:V1",
    "MM-CAPABILITY-20261006:UOM:COMP001:MM-TO-M:V1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_hash(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def configure(database: Path) -> None:
    if database.resolve() != EXPECTED_DATABASE or not database.is_file():
        raise RuntimeError("FORMAL_DATABASE_TARGET_MISMATCH")
    site.addsitedir(str(BACKEND / "venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database)
    os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
    os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
    os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    database = args.database.resolve()
    before_hash = sha256(database)
    configure(database)

    from django.db import connection, connections
    from django.db.migrations.recorder import MigrationRecorder
    from masterdata.material_identity import normalize_identity_text
    from masterdata.models import (
        CodeRule, ExternalIdentity, MasterDataWriteRequest, Material,
        MaterialCategory, UnitOfMeasure,
    )
    from masterdata.uom_governance import convert_uom_quantity
    from pde.models import (
        BOMItem, BOMItemSourceRequirement, BOMVersion, EngineeringCalculationDetail,
        EngineeringCalculationRecord, EngineeringDerivedFact,
        EngineeringMaterialRequirement, EngineeringRuleDefinition,
        LegacyInFlightOrderAdoption, LegacyInFlightOrderAdoptionRevocation,
        ProductBOM, ProductDesignItem,
    )
    from pde.order_bom_handoff_service import order_bom_handoff
    from sales.models import SalesOrder
    from system.models import Company, OrganizationOperatingAuditRecord, User

    connection.cursor().execute("PRAGMA query_only = ON")
    company = Company.objects.get(code="COMP001")
    category = MaterialCategory.objects.get(company_id=company.pk, code=CATEGORY_CODE)
    millimeter = UnitOfMeasure.objects.get(pk=15)
    meter = UnitOfMeasure.objects.get(pk=17)
    rule = CodeRule.objects.get(company_id=company.pk, entity_type="production_material")

    same_name = [
        row for row in MaterialCategory.objects.filter(company_id=company.pk, is_active=True)
        if normalize_identity_text(row.name) == normalize_identity_text(CATEGORY_NAME)
    ]
    same_code = list(MaterialCategory.objects.filter(code__iexact=CATEGORY_CODE))
    requests = list(MasterDataWriteRequest.objects.filter(
        idempotency_key__in=IDEMPOTENCY_KEYS,
    ).values(
        "id", "organization_id", "action_code", "entity_type", "idempotency_key",
        "status", "target_entity_id", "source_identity_id",
    ).order_by("id"))
    source_identity_ids = [row["source_identity_id"] for row in requests]
    identities = list(ExternalIdentity.objects.filter(pk__in=source_identity_ids).values(
        "id", "organization_id", "source_system", "source_type", "source_object_type",
        "external_id", "target_entity_type", "target_entity_id", "mapping_status",
    ).order_by("id"))
    audits = list(OrganizationOperatingAuditRecord.objects.filter(pk__in=(2733, 2734)).values(
        "id", "action_code", "actor__username", "organization_id", "target_type",
        "target_id", "target_label", "reason", "before_snapshot", "after_snapshot",
    ).order_by("id"))

    material_rows = list(Material.objects.filter(pk__in=(130, 136, 137, 138)).values(
        "id", "code", "name", "is_active", "category_id", "purpose",
        "specification", "base_uom_id", "application_notes",
    ).order_by("id"))
    mrc_rules = list(EngineeringRuleDefinition.objects.filter(pk__in=(15, 16, 17, 18, 19)).values(
        "id", "rule_code", "version", "rule_kind", "status",
    ).order_by("id"))
    requirements = list(EngineeringMaterialRequirement.objects.filter(pk__in=(3, 4, 5, 6, 7)).values(
        "id", "calculation_id", "source_detail_id", "material_id", "net_quantity",
        "uom_id", "trace",
    ).order_by("id"))
    for row in requirements:
        row["mappingNo"] = (row.pop("trace") or {}).get("mappingNo")

    order = SalesOrder.objects.get(order_no="SO202609180003")
    operator = User.objects.get(username="pce_plan_r12", is_active=True)
    handoff = order_bom_handoff(user=operator, order_id=order.pk, calculation_id=3)
    line1 = next(row for row in handoff["records"] if row["lineNo"] == 1)
    covered = sum(bool(row["formalMaterialRequirementCount"]) for row in line1["objects"])
    gate = handoff["bomHandoffStatus"]
    categories = {
        row["code"]: row
        for row in (gate.get("currentVersionMaterialCompleteness") or {}).get(
            "evaluatedCategories", []
        )
    }
    surface = categories.get("DOOR_LEAF_SURFACE_PANEL") or {}
    casing = categories.get("CASING_MATERIAL") or {}

    calculations = list(EngineeringCalculationRecord.objects.filter(pk__in=(3, 4, 5, 6)).values(
        "id", "calculation_no", "status", "result_hash",
    ).order_by("id"))
    detail_rows = list(EngineeringCalculationDetail.objects.values(
        "id", "calculation_id", "output_value", "uom_id",
    ).order_by("id"))
    fact_rows = list(EngineeringDerivedFact.objects.values(
        "id", "calculation_id", "fact_code", "value", "uom_id",
    ).order_by("id"))
    bom_versions = BOMVersion.objects.filter(
        source_calculation__sales_order_item__sales_order=order,
    )
    boms = {
        "productBom": ProductBOM.objects.filter(
            order_engineering_instance__sales_order_item__sales_order=order,
        ).count(),
        "bomVersion": bom_versions.count(),
        "bomItem": BOMItem.objects.filter(bom_version__in=bom_versions).count(),
        "sourceRequirementLink": BOMItemSourceRequirement.objects.filter(
            bom_item__bom_version__in=bom_versions,
        ).count(),
        "sourceCalculations": list(bom_versions.values_list("source_calculation_id", flat=True).order_by("source_calculation_id")),
    }
    adoption = LegacyInFlightOrderAdoption.objects.get(sales_order=order)
    cancelled = SalesOrder.objects.get(order_no="SO202610020004")

    with connection.cursor() as cursor:
        integrity = cursor.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = cursor.execute("PRAGMA foreign_key_check").fetchall()
        material_columns = [row[1] for row in cursor.execute("PRAGMA table_info(material)").fetchall()]

    result = {
        "database": str(database),
        "databaseSha256Before": before_hash,
        "company": {"id": company.pk, "code": company.code},
        "schema": {
            "materialPurpose": "purpose" in material_columns,
            "materialApplicationNotes": "application_notes" in material_columns,
            "migration0013Recorded": MigrationRecorder.Migration.objects.filter(
                app="masterdata", name="0013_material_application_notes_material_purpose",
            ).exists(),
        },
        "material": {
            "count": Material.objects.count(),
            "purposeNonEmptyCount": Material.objects.exclude(purpose="").count(),
            "applicationNotesNonEmptyCount": Material.objects.exclude(application_notes="").count(),
            "protectedRows": material_rows,
            "pineMaterialCount": Material.objects.filter(name__icontains="松木").count(),
        },
        "category": {
            "id": category.pk, "code": category.code, "name": category.name,
            "companyId": category.company_id, "active": category.is_active,
            "parentId": category.parent_id,
            "sameCodeCount": len(same_code), "activeNormalizedSameNameCount": len(same_name),
        },
        "uom": {
            "mm": {
                "id": millimeter.pk, "code": millimeter.code, "name": millimeter.name,
                "companyId": millimeter.company_id, "dimension": millimeter.dimension,
                "conversionBaseId": millimeter.conversion_base_id,
                "conversionFactor": str(millimeter.conversion_factor),
            },
            "m": {
                "id": meter.pk, "code": meter.code, "name": meter.name,
                "companyId": meter.company_id, "dimension": meter.dimension,
                "conversionBaseId": meter.conversion_base_id,
                "conversionFactor": str(meter.conversion_factor),
            },
            "1000mmToM": str(convert_uom_quantity(1000, source_uom=millimeter, target_uom=meter)),
            "1mToMm": str(convert_uom_quantity(1, source_uom=meter, target_uom=millimeter)),
        },
        "codeRule": {
            "id": rule.pk, "prefix": rule.prefix, "dateFormat": rule.date_format,
            "sequenceLength": rule.seq_length, "currentSequence": rule.current_seq,
        },
        "governedWrites": {
            "requests": requests, "sourceIdentities": identities, "audits": audits,
        },
        "protectedBusinessFacts": {
            "mrcRules": mrc_rules,
            "requirements": requirements,
            "designItemCount": ProductDesignItem.objects.filter(
                sales_order_item__sales_order=order,
            ).count(),
            "calculations3to6": calculations,
            "calculationDetailCount": len(detail_rows),
            "calculationDetailHash": canonical_hash(detail_rows),
            "derivedFactCount": len(fact_rows),
            "derivedFactHash": canonical_hash(fact_rows),
            "legacyAdoption": {
                "id": adoption.pk, "adoptionNo": adoption.adoption_no,
                "revoked": LegacyInFlightOrderAdoptionRevocation.objects.filter(adoption=adoption).exists(),
            },
            "boms": boms,
            "line1": {
                "objectCount": line1["objectCount"], "covered": covered,
                "surfacePanelCoverage": (
                    f"{surface.get('coveredDesignItemCount', 0)}/"
                    f"{surface.get('applicableDesignItemCount', 0)}"
                ),
                "casingRequirementCoverage": (
                    f"{casing.get('coveredDesignItemCount', 0)}/"
                    f"{casing.get('applicableDesignItemCount', 0)}"
                ),
                "gate": gate,
            },
            "cancelledOrder": {"id": cancelled.pk, "orderNo": cancelled.order_no, "status": cancelled.status},
        },
        "integrityCheck": integrity,
        "foreignKeyCheck": foreign_keys,
    }
    connections.close_all()
    after_hash = sha256(database)
    result["databaseSha256After"] = after_hash
    result["unchangedDuringReadback"] = after_hash == before_hash
    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
