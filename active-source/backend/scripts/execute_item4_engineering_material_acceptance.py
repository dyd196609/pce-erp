"""Authorize exactly the Item4 engineering-material acceptance; default is read-only."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from django.db import connection, transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrder, SalesOrderItem, SalesOrderItemSupplyAdmission
from sales.services import engineering_readiness_facts
from sales.supply_admission_service import supply_admission_facts
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition

from pde.management.commands.apply_saved_fact_material_requirement import _contract
from pde.models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringMaterialRequirement,
    EngineeringRuleDefinition,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductManufacturingOutput,
)
from pde.order_bom_handoff_service import order_bom_handoff
from pde.saved_fact_material_requirement_service import (
    apply_saved_fact_material_requirement,
    readback_saved_fact_material_requirement,
)


DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
CONTRACT_DIR = Path(__file__).resolve().parents[2] / (
    "docs/governance/evidence/"
    "SO202609180003_ITEM4_ENGINEERING_MATERIAL_ACCEPTANCE_20261012/contracts"
)
CONTRACT_FILES = (
    "design-item-6-material-130.json",
    "design-item-7-material-130.json",
    "design-item-8-material-130.json",
)
ACTOR = "pce_plan_r12"
ORDER_ID = 3
ITEM_ID = 4
CALCULATION_ID = 4
MATERIAL_ID = 130
SOURCE_EXTERNAL_IDENTITY_ID = 51
DESIGN_ITEM_IDS = (6, 7, 8)
GROUP_ACTION = "production.engineering.material_acceptance.confirm"
GROUP_OBJECT = "SalesOrderItemEngineeringMaterialAcceptance"
GROUP_KEY = "SO202609180003-ITEM4-ENGINEERING-MATERIAL-ACCEPTANCE-V1"
REASON = (
    "SO202609180003 Item4工程材料承接人工确认：DesignItem6/7/8统一承接"
    "Material130，主体板材含60×18、50×18线条范围；不拆分饰面/封边材料；"
    "数量只引用Calculation4已保存净面积，不重算、不加损耗、不创建Demand/BOM。"
)
EXPECTED_DELTAS = {
    "pde_engineering_rule_definition": 3,
    "pde_engineering_material_requirement": 3,
    "masterdata_external_identity": 6,
    "masterdata_write_request": 7,
    "system_organization_operating_audits": 13,
    "business_state_transitions": 1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def model_snapshot(model, pk: int) -> dict:
    row = model.objects.filter(pk=pk).values().first()
    assert row is not None, f"protected_object_missing:{model.__name__}:{pk}"
    return {"values": row, "sha256": payload_hash(row)}


def frozen_snapshot() -> dict:
    return {
        "salesOrderItem3": model_snapshot(SalesOrderItem, 3),
        "salesOrderItem4": model_snapshot(SalesOrderItem, 4),
        "item4SupplyAdmission": model_snapshot(SalesOrderItemSupplyAdmission, 2),
        "oei3": model_snapshot(OrderEngineeringInstance, 3),
        "baseline2": model_snapshot(OrderEngineeringBaseline, 2),
        "calculation4": model_snapshot(EngineeringCalculationRecord, 4),
        "material130": model_snapshot(Material, 130),
        "externalIdentity51": model_snapshot(ExternalIdentity, 51),
    }


def protected_counts() -> dict:
    return {
        "demand": Demand.objects.count(),
        "planningRequirement": PlanningRequirement.objects.count(),
        "bomVersion": BOMVersion.objects.count(),
        "manufacturingOutput": ProductManufacturingOutput.objects.count(),
    }


def physical_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        rows = {}
        for name in names:
            cursor.execute(f"SELECT * FROM {connection.ops.quote_name(name)}")
            rows[name] = Counter(
                json.dumps(row, ensure_ascii=False, default=str) for row in cursor.fetchall()
            )
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema_hash = hashlib.sha256(canonical(cursor.fetchall()).encode("utf-8")).hexdigest()
    return rows, schema_hash


def compare_physical(before, after, *, wrote: bool) -> dict:
    old_rows, old_schema = before
    new_rows, new_schema = after
    assert old_schema == new_schema, "schema_changed"
    assert old_rows.keys() == new_rows.keys(), "table_set_changed"
    changes = {}
    sequence_changes = {}
    for table, rows in old_rows.items():
        current = new_rows[table]
        if current == rows:
            continue
        if table == "sqlite_sequence":
            assert wrote, "unexpected_sequence_change"
            old = {json.loads(row)[0]: json.loads(row)[1] for row in rows}
            new = {json.loads(row)[0]: json.loads(row)[1] for row in current}
            assert old.keys() == new.keys(), "sequence_table_set_changed"
            for name, old_value in old.items():
                delta = new[name] - old_value
                if delta:
                    assert name in EXPECTED_DELTAS, f"protected_sequence_changed:{name}"
                    assert delta == EXPECTED_DELTAS[name], f"unexpected_sequence_delta:{name}:{delta}"
                    sequence_changes[name] = delta
            continue
        assert wrote and table in EXPECTED_DELTAS, f"protected_table_changed:{table}"
        assert not (rows - current), f"existing_row_changed_or_removed:{table}"
        delta = sum(current.values()) - sum(rows.values())
        assert delta == EXPECTED_DELTAS[table], f"unexpected_append_count:{table}:{delta}"
        changes[table] = {
            "before": sum(rows.values()),
            "after": sum(current.values()),
            "added": delta,
        }
    assert set(changes) == (set(EXPECTED_DELTAS) if wrote else set()), "unexpected_write_set"
    return {
        "schemaSha256": old_schema,
        "physicalTableCount": len(old_rows),
        "allExistingRowsPreserved": True,
        "changes": changes,
        "sequenceChanges": sequence_changes,
    }


def load_contracts():
    return [
        _contract(json.loads((CONTRACT_DIR / name).read_text(encoding="utf-8")))
        for name in CONTRACT_FILES
    ]


def item4_classifications(handoff: dict) -> list[dict]:
    rows = handoff["materialRequirementPreview"]["classifications"]
    return [row for row in rows if row["designItemId"] in DESIGN_ITEM_IDS]


def group_request_payload(results: list[dict]) -> dict:
    return {
        "serviceCode": "PCE-ITEM4-ENGINEERING-MATERIAL-ACCEPTANCE-V1",
        "orderId": ORDER_ID,
        "orderNo": "SO202609180003",
        "salesOrderItemId": ITEM_ID,
        "calculationId": CALCULATION_ID,
        "designItemIds": list(DESIGN_ITEM_IDS),
        "materialId": MATERIAL_ID,
        "sourceExternalIdentityId": SOURCE_EXTERNAL_IDENTITY_ID,
        "materialRole": "主体板材（含确认线条范围）",
        "includedTrimScopes": ["60×18", "50×18"],
        "requirementIds": [row["requirement"]["requirementId"] for row in results],
        "mappingIds": [row["requirement"]["mapping"]["id"] for row in results],
        "quantityContract": "CALCULATION4_SAVED_NET_AREA_ONLY",
        "lossRateStatus": "NOT_MAINTAINED",
        "finalProcurementQuantity": False,
        "demandCreated": False,
        "planningRequirementCreated": False,
        "bomVersionCreated": False,
        "manufacturingOutputCreated": False,
    }


def create_or_read_group_confirmation(*, user, results: list[dict]) -> dict:
    source_identity = ExternalIdentity.objects.select_for_update().get(
        pk=SOURCE_EXTERNAL_IDENTITY_ID,
        organization_id=user.company_id,
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
        target_entity_type="materials",
        target_entity_id=str(MATERIAL_ID),
    )
    request = group_request_payload(results)
    request_hash = payload_hash(request)
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=user.company_id,
        action_code=GROUP_ACTION,
        entity_type=GROUP_OBJECT,
        idempotency_key=GROUP_KEY,
    ).first()
    if ledger:
        assert ledger.status == MasterDataWriteRequest.Status.COMMITTED
        assert ledger.request_hash == request_hash
        assert ledger.source_identity_id == source_identity.pk
        transition = BusinessStateTransition.objects.get(
            pk=(ledger.result or {})["businessStateTransitionId"],
            object_type=GROUP_OBJECT,
            object_id=ITEM_ID,
            target_state="CONFIRMED",
        )
        audit = OrganizationOperatingAuditRecord.objects.get(
            pk=(ledger.result or {})["auditId"],
            action_code=GROUP_ACTION,
            target_type=GROUP_OBJECT,
            target_id=ITEM_ID,
        )
        return {
            "idempotent": True,
            "businessWriteCount": 0,
            "ledgerId": ledger.pk,
            "auditId": audit.pk,
            "businessStateTransitionId": transition.pk,
            "status": transition.target_state,
            "request": request,
        }
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=GROUP_ACTION,
        actor=user,
        organization_id=user.company_id,
        target_type=GROUP_OBJECT,
        target_id=ITEM_ID,
        target_label="SO202609180003 / Item4 工程材料承接"[:200],
        reason=REASON[:300],
        before_snapshot={
            "materialAcceptanceStatus": "MISSING_MATERIAL",
            "designItemIds": list(DESIGN_ITEM_IDS),
        },
        after_snapshot={
            **request,
            "materialAcceptanceStatus": "CONFIRMED",
            "factSource": "server",
            "operatorId": user.pk,
        },
    )
    transition = record_projected_business_transition(
        object_type=GROUP_OBJECT,
        object_id=ITEM_ID,
        source_state="MISSING_MATERIAL",
        target_state="CONFIRMED",
        action_code=GROUP_ACTION,
        operator=user,
        reason=REASON[:240],
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        allowed_transitions={("MISSING_MATERIAL", "CONFIRMED")},
    )
    ledger = MasterDataWriteRequest.objects.create(
        organization_id=user.company_id,
        action_code=GROUP_ACTION,
        entity_type=GROUP_OBJECT,
        idempotency_key=GROUP_KEY,
        request_hash=request_hash,
        source_identity=source_identity,
        status=MasterDataWriteRequest.Status.COMMITTED,
        target_entity_id=str(ITEM_ID),
        result={
            "salesOrderItemId": ITEM_ID,
            "status": "CONFIRMED",
            "auditId": audit.pk,
            "businessStateTransitionId": transition.pk,
            "requirementIds": request["requirementIds"],
            "mappingIds": request["mappingIds"],
        },
        audit_metadata={
            "authorizationReference": "《SO202609180003 Item4工程材料承接确认实施指令》",
            "operatorId": user.pk,
        },
    )
    return {
        "idempotent": False,
        "businessWriteCount": 3,
        "ledgerId": ledger.pk,
        "auditId": audit.pk,
        "businessStateTransitionId": transition.pk,
        "status": transition.target_state,
        "request": request,
    }


def assert_target_facts(*, order, item, user, frozen_before, counts_before):
    assert order.order_no == "SO202609180003" and order.status == "approved"
    assert item.pk == ITEM_ID and item.line_no == 2 and item.sales_order_id == ORDER_ID
    assert supply_admission_facts(item)["status"] == "CONFIRMED"
    assert supply_admission_facts(item)["supplyBranch"] == "MAKE"
    calculation = EngineeringCalculationRecord.objects.get(pk=CALCULATION_ID)
    assert calculation.sales_order_item_id == ITEM_ID and calculation.status == "completed"
    material = Material.objects.select_related("base_uom").get(pk=MATERIAL_ID)
    assert material.code == "MAT202608000048" and material.name == "清水封闭实木多层板"
    assert material.base_uom.code == "m2" and material.base_uom.symbol == "m²"
    identity = ExternalIdentity.objects.get(pk=SOURCE_EXTERNAL_IDENTITY_ID)
    assert identity.external_id.endswith("CODE:QSFB4601001")
    assert identity.target_entity_type == "materials" and identity.target_entity_id == "130"
    assert identity.mapping_status == ExternalIdentity.MappingStatus.MATCH
    assert frozen_snapshot() == frozen_before, "protected_object_changed"
    assert protected_counts() == counts_before, "forbidden_object_created"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--backup")
    args = parser.parse_args()
    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    assert os.environ.get("PCE_DATABASE_IDENTITY") == "PDE-OPERABLE-ACCEPTANCE-20260912"
    connection.ensure_connection()
    before_sha = sha256(DATABASE)
    if args.execute_authorized_item4:
        assert args.expected_sha256 and args.backup, "write_requires_expected_sha_and_backup"
        assert before_sha == args.expected_sha256.upper(), "database_sha_changed_before_write"
        assert sha256(Path(args.backup)) == before_sha, "backup_sha_mismatch"
    physical_before = physical_snapshot()
    frozen_before = frozen_snapshot()
    counts_before = protected_counts()
    user = User.objects.get(username=ACTOR, is_active=True, is_superuser=False)
    order = SalesOrder.objects.get(pk=ORDER_ID)
    item = order.items.get(pk=ITEM_ID)
    item3_before = supply_admission_facts(order.items.get(pk=3))
    readiness_before = engineering_readiness_facts(order)
    handoff_before = order_bom_handoff(user=user, order_id=ORDER_ID)
    classifications_before = item4_classifications(handoff_before)
    contracts = load_contracts()
    assert [row.design_item_no for row in contracts] == [
        "SO202609180003-DES-02-SRC-0008",
        "SO202609180003-DES-02-SRC-0009",
        "SO202609180003-DES-02-SRC-0010",
    ]
    assert_target_facts(
        order=order, item=item, user=user,
        frozen_before=frozen_before, counts_before=counts_before,
    )
    existing_group = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code=GROUP_ACTION,
        entity_type=GROUP_OBJECT,
        idempotency_key=GROUP_KEY,
    ).exists()
    if not existing_group:
        assert {row["status"] for row in classifications_before} == {"MISSING_MATERIAL"}
        assert len(classifications_before) == 3
        assert not EngineeringRuleDefinition.objects.filter(
            rule_code__in=[row.mapping_rule_code for row in contracts]
        ).exists(), "partial_mapping_state_detected"
        assert not EngineeringMaterialRequirement.objects.filter(
            calculation_id=CALCULATION_ID,
            trace__designItemId__in=DESIGN_ITEM_IDS,
        ).exists(), "partial_requirement_state_detected"
    results = []
    group = None
    if args.execute_authorized_item4 or existing_group:
        with transaction.atomic():
            results = [
                apply_saved_fact_material_requirement(user=user, contract=contract)
                for contract in contracts
            ]
            group = create_or_read_group_confirmation(user=user, results=results)
            wrote = not existing_group
            assert all(row["idempotent"] is (not wrote) for row in results)
            assert group["idempotent"] is (not wrote)
            assert_target_facts(
                order=order, item=item, user=user,
                frozen_before=frozen_before, counts_before=counts_before,
            )
            compare_physical(physical_before, physical_snapshot(), wrote=wrote)
    else:
        previews = [
            readback_saved_fact_material_requirement(user=user, contract=contract)
            if EngineeringRuleDefinition.objects.filter(
                company_id=user.company_id,
                rule_code=contract.mapping_rule_code,
                version=contract.mapping_version,
            ).exists()
            else None
            for contract in contracts
        ]
        assert previews == [None, None, None]
    wrote = bool(args.execute_authorized_item4 and not existing_group)
    if wrote:
        assert group and group["status"] == "CONFIRMED"
    if existing_group or wrote:
        readbacks = [
            readback_saved_fact_material_requirement(user=user, contract=contract)
            for contract in contracts
        ]
        replay_physical = physical_snapshot()
        with transaction.atomic():
            replay_results = [
                apply_saved_fact_material_requirement(user=user, contract=contract)
                for contract in contracts
            ]
            replay_group = create_or_read_group_confirmation(user=user, results=replay_results)
            assert all(row["idempotent"] and row["businessWriteCount"] == 0 for row in replay_results)
            assert replay_group["idempotent"] and replay_group["businessWriteCount"] == 0
        assert physical_snapshot() == replay_physical, "idempotent_replay_wrote_data"
    else:
        readbacks, replay_results, replay_group = [], [], None
    handoff_after = order_bom_handoff(user=user, order_id=ORDER_ID)
    classifications_after = item4_classifications(handoff_after)
    readiness_after = engineering_readiness_facts(order)
    if existing_group or wrote:
        assert len(classifications_after) == 3
        assert {row["status"] for row in classifications_after} == {"READY_FOR_REQUIREMENT"}
        assert all(row["applicableMappingIds"] for row in classifications_after)
        assert all(row["readbackMatch"] for row in readbacks)
        assert all(row["requirement"]["materialId"] == MATERIAL_ID for row in readbacks)
        assert all(row["requirement"]["grossQuantity"] is None for row in readbacks)
        assert all(row["requirement"]["scrapRateStatus"] == "not_maintained" for row in readbacks)
        assert all(row["requirement"]["xUsedAsMaterialQuantityBasis"] for row in readbacks)
    assert supply_admission_facts(order.items.get(pk=3)) == item3_before
    assert_target_facts(
        order=order, item=item, user=user,
        frozen_before=frozen_before, counts_before=counts_before,
    )
    physical_after = physical_snapshot()
    protection = compare_physical(physical_before, physical_after, wrote=wrote)
    connection.close()
    after_sha = sha256(DATABASE)
    assert wrote or before_sha == after_sha, "read_only_run_changed_database"
    item4_readiness = next(row for row in readiness_after["lines"] if row["salesOrderItemId"] == ITEM_ID)
    first_blocker = None
    if item4_readiness["blockers"]:
        first_blocker = {
            "code": "ORDER_DEMAND_MANUFACTURING_NOT_READY",
            "salesOrderItemId": ITEM_ID,
            "engineeringBlockerCode": item4_readiness["engineeringBlockerCode"],
            "reason": item4_readiness["blockers"][0],
        }
    output = {
        "mode": "AUTHORIZED_FORMAL_ACTION" if wrote else "READ_ONLY",
        "database": str(DATABASE),
        "databaseIdentity": os.environ.get("PCE_DATABASE_IDENTITY"),
        "sha256Before": before_sha,
        "sha256After": after_sha,
        "backup": args.backup if wrote else None,
        "actor": {"id": user.pk, "username": user.username},
        "humanConfirmedFacts": {
            "salesOrderItemId": ITEM_ID,
            "designItemIds": list(DESIGN_ITEM_IDS),
            "materialId": MATERIAL_ID,
            "materialCode": "MAT202608000048",
            "materialName": "清水封闭实木多层板",
            "sourceExternalIdentityId": SOURCE_EXTERNAL_IDENTITY_ID,
            "sourceExternalCode": "QSFB4601001",
            "role": "主体板材（含确认线条范围）",
            "includedTrimScopes": ["60×18", "50×18"],
            "separateFinishMaterial": False,
            "separateEdgeMaterial": False,
        },
        "materialAcceptance": group,
        "classificationsBefore": classifications_before,
        "classificationsAfter": classifications_after,
        "requirements": [row["requirement"] for row in readbacks],
        "applyResults": results,
        "readOnlyIdempotentReplay": {
            "requirements": replay_results,
            "group": replay_group,
        } if replay_group else None,
        "businessStateTransitions": list(
            BusinessStateTransition.objects.filter(
                object_type=GROUP_OBJECT, object_id=ITEM_ID,
            ).values()
        ),
        "audits": list(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code__in=(GROUP_ACTION, "production.engineering.material_requirement.create"),
                target_id__in=([ITEM_ID] + [row["requirement"]["requirementId"] for row in readbacks]),
            ).values("id", "action_code", "actor_id", "target_type", "target_id", "created_at")
        ),
        "protectedCountsBefore": counts_before,
        "protectedCountsAfter": protected_counts(),
        "frozenObjectHashesBefore": {key: row["sha256"] for key, row in frozen_before.items()},
        "frozenObjectHashesAfter": {
            key: row["sha256"] for key, row in frozen_snapshot().items()
        },
        "physicalProtection": protection,
        "readinessBefore": readiness_before,
        "readinessAfter": readiness_after,
        "firstBlocker": first_blocker,
        "item3Preserved": True,
        "calculationReexecuted": False,
        "demandCreationServiceCalled": False,
        "planningRequirementCreationServiceCalled": False,
        "bomVersionCreationServiceCalled": False,
        "manufacturingOutputCreationServiceCalled": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
