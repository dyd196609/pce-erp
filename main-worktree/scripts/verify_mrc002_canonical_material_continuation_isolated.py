"""Isolated full-chain gate for canonical Material convergence and MRC-002.

The named source database is copied before Django is configured.  All writes
run only against the temporary ``*-isolated.sqlite3`` copy; the source file is
hash-checked before and after the gate.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PROTECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
DESIGN_ITEM_NO = "SO202609180003-DES-01-SRC-0004"
DESIGN_IDEMPOTENCY_KEY = "SO202609180003:DES0004:MATERIAL-111-TO-130:V1"
DESIGN_REASON = (
    "用户确认门板正式用料为“清水封闭实木多层板”；DES-01-SRC-0004当前引用"
    "“清水开放实木多层板”与真实业务材料事实不一致。LC-M045属于色板编号，"
    "“清水封闭”属于表面工艺，二者均不作为板材Master身份推导依据。"
    "本次仅纠正门扇板材Material引用，不修改颜色、色板或油漆工艺事实。"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )


def configure(database: Path) -> None:
    if database == PROTECTED_DATABASE or not database.name.endswith("isolated.sqlite3"):
        raise RuntimeError("Django may only open an explicit isolated database copy")
    site.addsitedir(str(BACKEND / "venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database)
    for key in (
        "PCE_DATABASE_IDENTITY",
        "PCE_RUNTIME_PROFILE",
        "PCE_NON_PRODUCTION_ACCEPTANCE",
        "PCE_RUNTIME_LAUNCHER_VERIFIED",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def model_rows(model, queryset=None):
    queryset = queryset if queryset is not None else model.objects.all()
    fields = [field.attname for field in model._meta.concrete_fields]
    return list(queryset.values(*fields).order_by("pk"))


def material_rows():
    from masterdata.models import Material

    return model_rows(Material, Material.objects.filter(pk__in=(130, 136, 137, 138)))


def calculation_snapshot():
    from pde.models import (
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
    )

    calculations = model_rows(
        EngineeringCalculationRecord,
        EngineeringCalculationRecord.objects.filter(pk__in=(1, 2, 3, 4, 5, 6)),
    )
    details = model_rows(EngineeringCalculationDetail)
    facts = model_rows(EngineeringDerivedFact)
    return {
        "calculationHash": hashlib.sha256(canonical(calculations).encode()).hexdigest(),
        "detailCount": len(details),
        "detailHash": hashlib.sha256(canonical(details).encode()).hexdigest(),
        "factCount": len(facts),
        "factHash": hashlib.sha256(canonical(facts).encode()).hexdigest(),
        "detailCounts3to6": {
            str(calculation_id): sum(
                row["calculation_id"] == calculation_id for row in details
            )
            for calculation_id in (3, 4, 5, 6)
        },
        "factCounts3to6": {
            str(calculation_id): sum(
                row["calculation_id"] == calculation_id for row in facts
            )
            for calculation_id in (3, 4, 5, 6)
        },
    }


def mrc001_snapshot():
    from masterdata.models import ExternalIdentity, MasterDataWriteRequest
    from pde.models import EngineeringMaterialRequirement, EngineeringRuleDefinition
    from system.models import OrganizationOperatingAuditRecord

    return {
        "mapping": model_rows(
            EngineeringRuleDefinition,
            EngineeringRuleDefinition.objects.filter(pk=15),
        ),
        "requirement": model_rows(
            EngineeringMaterialRequirement,
            EngineeringMaterialRequirement.objects.filter(pk=3),
        ),
        "audits": model_rows(
            OrganizationOperatingAuditRecord,
            OrganizationOperatingAuditRecord.objects.filter(pk__in=(2706, 2707, 2708, 2709)),
        ),
        "actionRequests": model_rows(
            MasterDataWriteRequest,
            MasterDataWriteRequest.objects.filter(pk__in=(2040, 2041)),
        ),
        "externalIdentities": model_rows(
            ExternalIdentity,
            ExternalIdentity.objects.filter(pk__in=(2041, 2042)),
        ),
    }


def design_history(item):
    from pde.models import ProductDesignRevision

    return model_rows(
        ProductDesignRevision,
        ProductDesignRevision.objects.filter(design_item=item),
    )


def protected_design_shape(revision) -> dict:
    master_matches = dict(revision.master_match_results or {})
    master_matches.pop("material", None)
    return {
        "designNature": revision.design_nature,
        "designLength": str(revision.design_length),
        "designWidth": str(revision.design_width),
        "designThickness": str(revision.design_thickness),
        "designUomId": revision.design_uom_id,
        "materialProcessTypeId": revision.material_process_type_id,
        "paintProcessTypeId": revision.paint_process_type_id,
        "edgeMethodId": revision.edge_method_id,
        "designData": revision.design_data,
        "sourceProvenance": revision.source_provenance,
        "masterMatchesExceptMaterial": master_matches,
        "legacySourceRecordId": revision.legacy_source_record_id,
    }


def protected_order_snapshot():
    from pde.models import (
        EngineeringCalculationRecord,
        OrderEngineeringInstance,
        ProductBOM,
        ProductDesignItem,
    )
    from sales.models import SalesOrder

    order = SalesOrder.objects.get(order_no="SO202610020004")
    return {
        "id": order.pk,
        "status": order.status,
        "sourceCount": ProductDesignItem.objects.filter(
            sales_order_item__sales_order=order,
        ).values("source_record_id").distinct().count(),
        "designItemCount": ProductDesignItem.objects.filter(
            sales_order_item__sales_order=order,
        ).count(),
        "instances": list(OrderEngineeringInstance.objects.filter(
            sales_order_item__sales_order=order,
        ).values("id", "instance_no", "status").order_by("id")),
        "activeInstanceCount": OrderEngineeringInstance.objects.filter(
            sales_order_item__sales_order=order,
        ).exclude(status="inactive").count(),
        "calculations": list(EngineeringCalculationRecord.objects.filter(
            sales_order_item__sales_order=order,
        ).values("id", "calculation_no", "status").order_by("id")),
        "boms": list(ProductBOM.objects.filter(
            order_engineering_instance__sales_order_item__sales_order=order,
        ).values("id", "bom_code").order_by("id")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    args = parser.parse_args()
    source = args.database.resolve()
    contract_path = args.contract.resolve()
    if not source.is_file() or not contract_path.is_file():
        raise RuntimeError("database or contract is missing")
    source_hash_before = sha256(source)
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(
        prefix="pce-mrc002-canonical-", ignore_cleanup_errors=True,
    ) as directory:
        isolated = Path(directory) / "mrc002-canonical-isolated.sqlite3"
        shutil.copy2(source, isolated)
        if sha256(isolated) != source_hash_before:
            raise RuntimeError("isolated database copy hash mismatch")
        configure(isolated)

        from django.db import connections
        from django.db.migrations.recorder import MigrationRecorder
        from masterdata.canonical_material_convergence_service import (
            apply_canonical_material_convergence,
            material_reference_inventory,
            readback_canonical_material_convergence,
        )
        from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
        from pde.engineering_calculation_service import OrderEngineeringClosureService
        from pde.management.commands.apply_saved_fact_material_requirement import _contract
        from pde.models import (
            BOMItem,
            BOMItemSourceRequirement,
            BOMVersion,
            EngineeringDerivedFact,
            EngineeringMaterialRequirement,
            EngineeringRuleDefinition,
            LegacyInFlightOrderAdoption,
            ProductBOM,
            ProductDesignCompletionRecord,
            ProductDesignItem,
            ProductDesignRevision,
        )
        from pde.order_bom_handoff_service import order_bom_handoff
        from pde.product_design_service import ProductDesignError, save_design_content
        from pde.saved_fact_material_requirement_service import (
            SavedFactMaterialRequirementError,
            apply_saved_fact_material_requirement,
            preview_saved_fact_material_requirement,
            readback_saved_fact_material_requirement,
        )
        from sales.models import SalesOrder
        from system.models import (
            OrganizationOperatingAuditRecord,
            Permission,
            RolePermission,
            User,
            UserRoleScopeAssignment,
        )

        tests = []

        def check(name: str, condition: bool, evidence=None):
            if not condition:
                raise AssertionError(f"{name}: {canonical(evidence)}")
            tests.append({"name": name, "status": "PASS", "evidence": evidence})

        contract = _contract(contract_payload)
        material_actor = User.objects.get(username="emd_emp047", is_active=True)
        design_actor = User.objects.get(username="admin", is_active=True)
        requirement_actor = User.objects.get(username="pce_plan_r12", is_active=True)
        order = SalesOrder.objects.get(order_no=contract.order_no)
        item = ProductDesignItem.objects.get(item_no=DESIGN_ITEM_NO)
        old_latest = item.design_revisions.order_by("-revision", "-pk").first()

        initial_materials = material_rows()
        initial_material_130 = next(row for row in initial_materials if row["id"] == 130)
        initial_inventory = material_reference_inventory()
        initial_mrc001 = mrc001_snapshot()
        initial_history = design_history(item)
        initial_shape = protected_design_shape(old_latest)
        initial_calculations = calculation_snapshot()
        initial_pdi_count = ProductDesignItem.objects.count()
        initial_completion_count = ProductDesignCompletionRecord.objects.count()
        initial_adoption = model_rows(LegacyInFlightOrderAdoption)
        initial_cancelled_order = protected_order_snapshot()
        initial_permission_state = {
            "permissions": model_rows(Permission),
            "rolePermissions": model_rows(RolePermission),
            "roleScopes": model_rows(UserRoleScopeAssignment),
        }
        migration_before = sorted(MigrationRecorder.Migration.objects.values_list("app", "name"))
        migration_files_before = sorted(
            str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")
        )
        bom_before = {
            "headers": model_rows(ProductBOM),
            "versions": model_rows(BOMVersion),
            "items": model_rows(BOMItem),
            "links": model_rows(BOMItemSourceRequirement),
        }
        protected_0005_0007 = {
            target: design_history(ProductDesignItem.objects.get(item_no=target))
            for target in (
                "SO202609180003-DES-01-SRC-0005",
                "SO202609180003-DES-01-SRC-0006",
                "SO202609180003-DES-01-SRC-0007",
            )
        }

        check(
            "01 duplicate Materials have zero formal business references",
            all(
                initial_inventory["counts"][str(material_id)]["formalBusinessReferenceCount"] == 0
                for material_id in (136, 137, 138)
            ),
            initial_inventory["counts"],
        )
        check(
            "02 duplicate provenance is preserved but is not a downstream business reference",
            all(
                initial_inventory["counts"][str(material_id)]["externalIdentityCount"] == 1
                and initial_inventory["counts"][str(material_id)]["historicalWriteRequestCount"] == 2
                and initial_inventory["counts"][str(material_id)]["historicalAuditCount"] == 2
                for material_id in (136, 137, 138)
            ),
        )
        check(
            "03 canonical Material is active and the four business identities match",
            initial_material_130["is_active"] is True
            and len({
                canonical({
                    key: value for key, value in row.items()
                    if key not in {"id", "code", "is_active", "created_at", "updated_at"}
                })
                for row in initial_materials
            }) == 1,
        )
        check(
            "04 MRC-001 anchors exist before the test",
            len(initial_mrc001["mapping"]) == 1
            and initial_mrc001["mapping"][0]["id"] == 15
            and len(initial_mrc001["requirement"]) == 1
            and initial_mrc001["requirement"][0]["id"] == 3
            and str(initial_mrc001["requirement"][0]["net_quantity"]) == "3.475472"
            and [row["id"] for row in initial_mrc001["audits"]] == [2706, 2707, 2708, 2709],
        )
        check(
            "05 current calculation baseline is 396 and Calculation 3-6 remains 388",
            initial_calculations["detailCount"] == 396
            and initial_calculations["factCount"] == 396
            and initial_calculations["detailCounts3to6"] == {"3": 85, "4": 51, "5": 248, "6": 4}
            and initial_calculations["factCounts3to6"] == {"3": 85, "4": 51, "5": 248, "6": 4},
            initial_calculations,
        )

        canonical_first = apply_canonical_material_convergence(user=material_actor)
        canonical_readback = readback_canonical_material_convergence(user=material_actor)
        connections.close_all()
        hash_after_canonical_first = sha256(isolated)
        canonical_replay = apply_canonical_material_convergence(user=material_actor)
        connections.close_all()
        check(
            "06 controlled Material deactivation uses the formal actor and preserves 130",
            canonical_first["materialWriteCount"] == 3
            and canonical_first["actor"]["account"] == "emd_emp047"
            and canonical_first["actor"]["responsibilityCode"] == "ENTERPRISE_MASTER_DATA_MAINTAINER"
            and canonical_readback["canonicalMaterial"]["is_active"] is True
            and all(not row["material"]["is_active"] for row in canonical_readback["duplicates"]),
            canonical_first,
        )
        check(
            "07 Material deactivation replay is byte-for-byte zero-write",
            canonical_replay["idempotent"] is True
            and canonical_replay["businessWriteCount"] == 0
            and sha256(isolated) == hash_after_canonical_first,
        )
        check(
            "08 every deactivation has Audit, actor, reason, before/after, ledger, and source identity",
            all(
                row["auditId"] and row["actionRequestId"] and row["sourceIdentityId"]
                and row["before"]["state"]["is_active"] is True
                and row["after"]["state"]["is_active"] is False
                for row in canonical_readback["duplicates"]
            ),
            canonical_readback,
        )
        check(
            "09 Material 130 full row and MRC-001 remain unchanged after canonicalization",
            next(row for row in material_rows() if row["id"] == 130) == initial_material_130
            and mrc001_snapshot() == initial_mrc001,
        )

        item.refresh_from_db()
        _, design_replayed = save_design_content(
            user=design_actor,
            payload={
                "designItemIds": [item.pk],
                "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL",
                "reason": DESIGN_REASON,
                "designData": {"materialId": 130},
            },
            idempotency_key=DESIGN_IDEMPOTENCY_KEY,
        )
        item.refresh_from_db()
        new_latest = item.design_revisions.order_by("-revision", "-pk").first()
        design_ledger = MasterDataWriteRequest.objects.get(
            action_code="pde.product_design.content.save",
            idempotency_key=DESIGN_IDEMPOTENCY_KEY,
        )
        design_audit = OrganizationOperatingAuditRecord.objects.get(
            pk=design_ledger.result["auditId"],
        )
        check(
            "10 design correction appends formal Revision 9 from Material 111 to 130",
            design_replayed is False
            and old_latest.revision == 8 and old_latest.material_id == 111
            and new_latest.revision == 9 and new_latest.material_id == 130
            and new_latest.created_by_id == design_actor.pk
            and design_audit.actor_id == design_actor.pk,
            {"revisionId": new_latest.pk, "auditId": design_audit.pk, "actor": design_actor.username},
        )
        check(
            "11 historical Revisions 1-8 are byte-for-byte preserved",
            design_history(item)[:len(initial_history)] == initial_history
            and [row["revision"] for row in initial_history] == list(range(1, 9)),
        )
        check(
            "12 only the Material dimension changed",
            protected_design_shape(new_latest) == initial_shape
            and new_latest.design_data["finishOrColor"] == "柚木直纹，封闭/LC-M045"
            and new_latest.design_data["processConfigurationCode"] == "QSFB/FM",
            protected_design_shape(new_latest),
        )

        item.refresh_from_db()
        try:
            save_design_content(
                user=design_actor,
                payload={
                    "designItemIds": [item.pk],
                    "expectedVersions": {str(item.pk): item.version},
                    "designNature": "FORMAL",
                    "reason": "隔离测试：停用非Canonical Material不得进入新设计修订",
                    "designData": {"materialId": 136},
                },
                idempotency_key="ISOLATED:DES0004:NONCANONICAL-136:REJECT",
            )
        except ProductDesignError as exc:
            noncanonical_design_error = exc.code
        else:
            raise AssertionError("inactive noncanonical Material unexpectedly accepted")
        check(
            "13 inactive noncanonical Material cannot enter a new design or Requirement chain",
            noncanonical_design_error == "DESIGN_MASTER_INVALID",
            noncanonical_design_error,
        )

        preview = preview_saved_fact_material_requirement(
            user=requirement_actor, contract=contract,
        )
        check(
            "14 MRC-002 preview uses exact R/S/U, formula, quantity, UOM, and legacy scope",
            preview["quantity"] == "3.155152"
            and preview["factCodesUsed"] == ["R", "S", "U"]
            and [row["value"] for row in preview["facts"]] == [
                "2002.000000", "788.000000", "1.000000",
            ]
            and preview["material"]["id"] == 130
            and preview["material"]["uom"] == "m2"
            and Decimal(preview["salesOrderItem"]["quantity"]) == Decimal("5")
            and preview["salesOrderItem"]["quantityMultiplierApplied"] is False
            and preview["legacyAdoption"]["lockedScope"],
            preview,
        )
        try:
            preview_saved_fact_material_requirement(
                user=requirement_actor,
                contract=replace(
                    contract,
                    mapping_no="MRC-002-NONCANONICAL-PROBE",
                    mapping_rule_code="MRM.SO202609180003.MRC-002-NONCANONICAL-PROBE",
                    material_id=136,
                    material_code="MAT202608000054",
                    idempotency_key="ISOLATED:MRC002:NONCANONICAL-136:REJECT",
                ),
            )
        except SavedFactMaterialRequirementError as exc:
            noncanonical_requirement_error = exc.code
        else:
            raise AssertionError("inactive noncanonical Material unexpectedly previewed")
        check(
            "15 noncanonical Material cannot create a new Requirement",
            noncanonical_requirement_error in {
                "DESIGN_MATERIAL_REFERENCE_MISMATCH", "MATERIAL_NOT_FOUND",
            },
            noncanonical_requirement_error,
        )

        first = apply_saved_fact_material_requirement(
            user=requirement_actor, contract=contract,
        )
        readback = readback_saved_fact_material_requirement(
            user=requirement_actor, contract=contract,
        )
        connections.close_all()
        hash_after_mrc002_first = sha256(isolated)
        replay = apply_saved_fact_material_requirement(
            user=requirement_actor, contract=contract,
        )
        connections.close_all()
        requirement = EngineeringMaterialRequirement.objects.get(
            pk=first["requirement"]["requirementId"],
        )
        mapping = EngineeringRuleDefinition.objects.get(
            pk=first["requirement"]["mapping"]["id"],
        )
        check(
            "16 MRC-002 released Mapping and exact Requirement are persisted",
            mapping.rule_code == "MRM.SO202609180003.MRC-002"
            and mapping.status == "released"
            and requirement.material_id == 130
            and requirement.net_quantity == Decimal("3.155152")
            and requirement.gross_quantity == Decimal("3.155152")
            and requirement.scrap_rate == 0
            and requirement.trace["structureRole"] == "DOOR_LEAF_SURFACE_PANEL"
            and requirement.trace["wUsedAsQuantityBasis"] is False
            and requirement.trace["xUsedAsMaterialQuantityBasis"] is False
            and requirement.trace["orderQuantityMultiplierApplied"] is False,
            first,
        )
        check(
            "17 MRC-002 readback and replay are exact and zero-write",
            readback["readbackMatch"] is True
            and replay["idempotent"] is True
            and replay["businessWriteCount"] == 0
            and sha256(isolated) == hash_after_mrc002_first,
        )

        direct_preview = OrderEngineeringClosureService.preview_bom(
            user=requirement_actor, calculation_id=3,
        )
        handoff = order_bom_handoff(user=requirement_actor, order_id=order.pk)
        line1 = next(row for row in handoff["records"] if row["lineNo"] == 1)
        missing = [
            row["objectNo"] for row in line1["objects"]
            if not row["formalMaterialRequirementCount"]
        ]
        check(
            "18 BOM preview is read-only, coverage is 2/5, and 0005 is first blocker",
            direct_preview["rowCount"] == 1
            and direct_preview["sourceRequirementCount"] == 2
            and direct_preview["rows"][0]["sourceRequirementIds"] == [3, 4]
            and Decimal(direct_preview["rows"][0]["quantity"]) == Decimal("6.630624")
            and line1["objectCount"] == 5
            and sum(bool(row["formalMaterialRequirementCount"]) for row in line1["objects"]) == 2
            and missing == [
                "SO202609180003-DES-01-SRC-0005",
                "SO202609180003-DES-01-SRC-0006",
                "SO202609180003-DES-01-SRC-0007",
            ],
            {"directPreview": direct_preview, "missing": missing},
        )
        check(
            "19 no BOM was generated and 0005-0007 were not modified",
            bom_before == {
                "headers": model_rows(ProductBOM),
                "versions": model_rows(BOMVersion),
                "items": model_rows(BOMItem),
                "links": model_rows(BOMItemSourceRequirement),
            }
            and protected_0005_0007 == {
                target: design_history(ProductDesignItem.objects.get(item_no=target))
                for target in protected_0005_0007
            },
        )

        final_calculations = calculation_snapshot()
        check(
            "20 calculations and saved facts remain byte-for-byte unchanged",
            final_calculations == initial_calculations,
        )
        check(
            "21 MRC-001, Material 130, 71 design items, and 71 completions are protected",
            mrc001_snapshot() == initial_mrc001
            and next(row for row in material_rows() if row["id"] == 130) == initial_material_130
            and ProductDesignItem.objects.count() == initial_pdi_count == 71
            and ProductDesignCompletionRecord.objects.count() == initial_completion_count == 71,
        )
        check(
            "22 Legacy Adoption and cancelled SO202610020004 remain unchanged",
            model_rows(LegacyInFlightOrderAdoption) == initial_adoption
            and protected_order_snapshot() == initial_cancelled_order
            and initial_cancelled_order["status"] == "cancelled"
            and initial_cancelled_order["sourceCount"] == 0
            and initial_cancelled_order["designItemCount"] == 0
            and initial_cancelled_order["activeInstanceCount"] == 0
            and all(
                row["status"] == "inactive"
                for row in initial_cancelled_order["instances"]
            )
            and not initial_cancelled_order["calculations"]
            and not initial_cancelled_order["boms"],
            initial_cancelled_order,
        )
        final_permission_state = {
            "permissions": model_rows(Permission),
            "rolePermissions": model_rows(RolePermission),
            "roleScopes": model_rows(UserRoleScopeAssignment),
        }
        migration_after = sorted(MigrationRecorder.Migration.objects.values_list("app", "name"))
        migration_files_after = sorted(
            str(path.relative_to(ROOT)) for path in ROOT.glob("backend/*/migrations/*.py")
        )
        check(
            "23 permissions, schema migration ledger, and migration files are unchanged",
            final_permission_state == initial_permission_state
            and migration_after == migration_before
            and migration_files_after == migration_files_before,
        )

        final_inventory = material_reference_inventory()
        final_materials = material_rows()
        source_hash_after = sha256(source)
        result = {
            "gate": "MRC-002 canonical Material continuation isolated gate",
            "status": "PASS",
            "testCount": len(tests),
            "tests": tests,
            "sourceDatabase": str(source),
            "sourceDatabaseSha256Before": source_hash_before,
            "sourceDatabaseSha256After": source_hash_after,
            "sourceDatabaseUnchanged": source_hash_before == source_hash_after,
            "canonicalization": {
                "firstApply": canonical_first,
                "readback": canonical_readback,
                "idempotentReplay": canonical_replay,
                "initialReferenceCounts": initial_inventory["counts"],
                "finalReferenceCounts": final_inventory["counts"],
                "finalMaterials": final_materials,
            },
            "designCorrection": {
                "priorRevisionId": old_latest.pk,
                "priorRevision": old_latest.revision,
                "priorMaterialId": old_latest.material_id,
                "newRevisionId": new_latest.pk,
                "newRevision": new_latest.revision,
                "newMaterialId": new_latest.material_id,
                "actor": design_actor.username,
                "auditId": design_audit.pk,
                "actionRequestId": design_ledger.pk,
                "reason": DESIGN_REASON,
            },
            "mrc002": {
                "preview": preview,
                "firstApply": first,
                "readback": readback,
                "idempotentReplay": replay,
            },
            "bomPreview": {
                "direct": direct_preview,
                "line1ObjectCount": line1["objectCount"],
                "coveredObjectCount": 2,
                "missingObjectNos": missing,
                "firstRealBlocker": missing[0],
            },
            "calculationBaseline": final_calculations,
            "protectedScope": {
                "mrc001": initial_mrc001,
                "productDesignItemCount": ProductDesignItem.objects.count(),
                "completionCount": ProductDesignCompletionRecord.objects.count(),
                "legacyAdoption": initial_adoption,
                "SO202610020004": initial_cancelled_order,
            },
            "schemaChange": False,
            "migrationExecuted": False,
            "permissionChanged": False,
            "bomGenerated": False,
        }
        if source_hash_before != source_hash_after:
            raise AssertionError("source database changed during isolated gate")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
