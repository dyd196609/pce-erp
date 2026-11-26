"""Audited, idempotent convergence of indistinguishable active Materials.

This module deliberately remains a thin guard around the existing canonical
``ProductionFoundationService.save("materials", ...)`` write primitive.  It
does not merge or delete records, rewrite downstream references, add schema,
or grant permissions.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import re

from django.apps import apps
from django.db import connection, models, transaction

from pde.production_foundation_service import ProductionFoundationService
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    PositionResponsibility,
)

from .models import ExternalIdentity, MasterDataWriteRequest, Material


SERVICE_CODE = "PCE-CANONICAL-MATERIAL-CONVERGENCE-V1"
ACTION_CODE = "production.master_data.material.maintain"
REQUIRED_RESPONSIBILITY = "ENTERPRISE_MASTER_DATA_MAINTAINER"
CANONICAL_MATERIAL_ID = 130
DUPLICATE_MATERIAL_IDS = (136, 137, 138)
REASON = (
    "Material 130/136/137/138在当前正式主数据中业务属性一致且无法区分；"
    "130已有正式MRC-001下游引用，136–138无正式引用。为消除Material Master歧义，"
    "保留130为唯一active Canonical Material，并受控停用136–138。历史记录不删除。"
)

_NON_IDENTITY_FIELDS = {"id", "code", "is_active", "created_at", "updated_at"}
_PROVENANCE_MODELS = {
    "masterdata.ExternalIdentity",
    "masterdata.MasterDataWriteRequest",
    "system.OrganizationOperatingAuditRecord",
}


class CanonicalMaterialConvergenceError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _fail(code: str, message: str, **details):
    raise CanonicalMaterialConvergenceError(code, message, details)


def _canonical_json(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )


def _hash(value) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _reference_gate_hash(inventory: dict) -> str:
    """Hash only immutable reference-gate evidence, not new audit/ledger rows."""

    return _hash({
        "formalCounts": {
            material_id: {
                key: counts[key]
                for key in (
                    "formalBusinessReferenceCount",
                    "directForeignKeyReferenceCount",
                    "semanticJsonReferenceCount",
                    "externalIdentityCount",
                )
            }
            for material_id, counts in inventory["counts"].items()
        },
        "directForeignKeys": inventory["directForeignKeys"],
        "semanticJsonReferences": inventory["semanticJsonReferences"],
        "absentModelTables": inventory["modelMaterialForeignKeysWithAbsentTables"],
    })


def _snapshot(instance: Material) -> dict:
    result = {}
    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.attname)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[field.attname] = value
    return result


def _business_identity(instance: Material) -> dict:
    return {
        key: value
        for key, value in _snapshot(instance).items()
        if key not in _NON_IDENTITY_FIELDS
    }


def _material_json_hits(value, *, material_ids_by_code: dict[str, int]) -> set[int]:
    """Find exact Material ids/codes only below keys with material semantics."""

    material_ids = set(material_ids_by_code.values())
    hits: set[int] = set()

    def visit(current, material_context=False):
        if isinstance(current, dict):
            for key, child in current.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                child_context = material_context or "material" in normalized
                visit(child, child_context)
            return
        if isinstance(current, (list, tuple)):
            for child in current:
                visit(child, material_context)
            return
        if not material_context or isinstance(current, bool) or current is None:
            return
        if isinstance(current, int) and current in material_ids:
            hits.add(current)
            return
        text = str(current).strip()
        if text in material_ids_by_code:
            hits.add(material_ids_by_code[text])
            return
        if text.isdigit() and int(text) in material_ids:
            hits.add(int(text))

    visit(value)
    return hits


def material_reference_inventory(material_ids=(CANONICAL_MATERIAL_ID, *DUPLICATE_MATERIAL_IDS)) -> dict:
    """Return exhaustive model-FK, semantic JSON, and provenance reference counts.

    Direct foreign keys and semantic JSON references are formal business
    references.  External identities, prior write requests, and audits are
    reported separately as historical provenance and are intentionally not a
    reason to erase or rewrite the historical Material.
    """

    ids = tuple(int(value) for value in material_ids)
    materials = {
        row.pk: row for row in Material.objects.filter(pk__in=ids).order_by("pk")
    }
    if set(materials) != set(ids):
        _fail(
            "MATERIAL_SCOPE_INCOMPLETE",
            "Canonical治理目标Material集合不完整。",
            expected=list(ids),
            actual=sorted(materials),
        )
    codes = {row.code: row.pk for row in materials.values()}
    existing_tables = set(connection.introspection.table_names())
    direct_fields = []
    absent_model_tables = []
    models_with_direct_material_fk = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, "concrete", False):
                continue
            if getattr(getattr(field, "remote_field", None), "model", None) is not Material:
                continue
            descriptor = {
                "model": model._meta.label,
                "table": model._meta.db_table,
                "field": field.name,
                "attname": field.attname,
                "onDelete": getattr(
                    getattr(field.remote_field, "on_delete", None),
                    "__name__",
                    str(getattr(field.remote_field, "on_delete", None)),
                ),
            }
            if model._meta.db_table not in existing_tables:
                absent_model_tables.append(descriptor)
                continue
            models_with_direct_material_fk.add(model)
            descriptor["counts"] = {
                str(material_id): model.objects.filter(
                    **{field.attname: material_id}
                ).count()
                for material_id in ids
            }
            direct_fields.append(descriptor)

    semantic_rows: dict[int, list[dict]] = defaultdict(list)
    for model in apps.get_models():
        if (
            model in models_with_direct_material_fk
            or model._meta.label in _PROVENANCE_MODELS
            or model._meta.db_table not in existing_tables
        ):
            continue
        json_fields = [
            field for field in model._meta.concrete_fields
            if isinstance(field, models.JSONField)
        ]
        if not json_fields:
            continue
        selected = ["pk", *(field.attname for field in json_fields)]
        for row in model.objects.values(*selected).iterator(chunk_size=250):
            for field in json_fields:
                for material_id in _material_json_hits(
                    row.get(field.attname), material_ids_by_code=codes,
                ):
                    semantic_rows[material_id].append({
                        "model": model._meta.label,
                        "table": model._meta.db_table,
                        "rowId": row["pk"],
                        "field": field.name,
                    })

    provenance = {}
    for material_id in ids:
        provenance[str(material_id)] = {
            "externalIdentities": list(ExternalIdentity.objects.filter(
                target_entity_id=str(material_id),
                target_entity_type__icontains="material",
            ).values(
                "id", "source_system", "source_type", "source_object_type",
                "external_id", "target_entity_type", "mapping_status",
            ).order_by("id")),
            "writeRequests": list(MasterDataWriteRequest.objects.filter(
                target_entity_id=str(material_id),
                entity_type__icontains="material",
            ).values(
                "id", "action_code", "entity_type", "status", "idempotency_key",
            ).order_by("id")),
            "audits": list(OrganizationOperatingAuditRecord.objects.filter(
                target_id=material_id,
                target_type__icontains="material",
            ).values("id", "action_code", "target_type", "reason").order_by("id")),
        }

    counts = {}
    for material_id in ids:
        direct_count = sum(
            row["counts"][str(material_id)] for row in direct_fields
        )
        json_count = len(semantic_rows.get(material_id, []))
        counts[str(material_id)] = {
            "formalBusinessReferenceCount": direct_count + json_count,
            "directForeignKeyReferenceCount": direct_count,
            "semanticJsonReferenceCount": json_count,
            "externalIdentityCount": len(
                provenance[str(material_id)]["externalIdentities"]
            ),
            "historicalWriteRequestCount": len(
                provenance[str(material_id)]["writeRequests"]
            ),
            "historicalAuditCount": len(provenance[str(material_id)]["audits"]),
        }
    return {
        "serviceCode": SERVICE_CODE,
        "materials": {
            str(row.pk): _snapshot(row) for row in materials.values()
        },
        "counts": counts,
        "directForeignKeys": direct_fields,
        "semanticJsonReferences": {
            str(material_id): rows
            for material_id, rows in sorted(semantic_rows.items())
        },
        "historicalProvenance": provenance,
        "modelMaterialForeignKeysWithAbsentTables": absent_model_tables,
    }


def _actor_context(user) -> dict:
    if not user or not user.is_authenticated or not user.is_active:
        _fail("FORMAL_ACTOR_REQUIRED", "Material治理必须由有效登录账户执行。")
    if user.is_superuser:
        _fail("ADMIN_BYPASS_FORBIDDEN", "Material治理禁止使用admin或超级管理员绕过。")
    employee = Employee.objects.select_related("position_ref").filter(
        user=user, status="active",
    ).first()
    position = employee.position_ref if employee else None
    responsibility = PositionResponsibility.objects.select_related(
        "responsibility",
    ).filter(
        position=position,
        active=True,
        responsibility__code=REQUIRED_RESPONSIBILITY,
        responsibility__status="ACTIVE",
        responsibility__is_active=True,
    ).first() if position and position.is_active else None
    if not employee or not position or not position.is_active or not responsibility:
        _fail(
            "MATERIAL_MASTER_RESPONSIBILITY_REQUIRED",
            "执行账户缺少在职员工、有效岗位或企业基础资料维护正式职责。",
        )
    decision = AuthorizationService.decide(
        user=user,
        action_code=ACTION_CODE,
        organization_id=user.company_id,
        business_object={"organizationId": user.company_id},
    )
    if not decision.get("allowed"):
        _fail(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "当前账户无权维护Material。"),
            authorization=decision,
        )
    return {
        "accountId": user.pk,
        "account": user.username,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "employeeName": employee.full_name,
        "positionId": position.pk,
        "positionCode": position.code,
        "responsibilityCode": responsibility.responsibility.code,
        "authorization": decision,
    }


def _source_identity(material: Material) -> ExternalIdentity:
    rows = list(ExternalIdentity.objects.select_for_update().filter(
        organization_id=material.company_id,
        target_entity_type="materials",
        target_entity_id=str(material.pk),
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).order_by("pk"))
    if len(rows) != 1:
        _fail(
            "MATERIAL_SOURCE_IDENTITY_NOT_UNIQUE",
            "待停用Material必须保留且唯一对应原正式来源身份。",
            materialId=material.pk,
            matchCount=len(rows),
        )
    return rows[0]


def _validate_scope(materials: dict[int, Material], inventory: dict) -> None:
    canonical = materials[CANONICAL_MATERIAL_ID]
    if not canonical.is_active:
        _fail("CANONICAL_MATERIAL_INACTIVE", "Material 130必须保持active。")
    expected_identity = _business_identity(canonical)
    differences = {}
    for material_id in DUPLICATE_MATERIAL_IDS:
        material = materials[material_id]
        actual_identity = _business_identity(material)
        if actual_identity != expected_identity:
            differences[str(material_id)] = {
                key: {"canonical": expected_identity.get(key), "duplicate": value}
                for key, value in actual_identity.items()
                if expected_identity.get(key) != value
            }
        count = inventory["counts"][str(material_id)]["formalBusinessReferenceCount"]
        if count:
            _fail(
                "DUPLICATE_MATERIAL_REFERENCED",
                "重复Material存在正式业务引用，禁止停用。",
                materialId=material_id,
                referenceCount=count,
                inventory=inventory,
            )
    if differences:
        _fail(
            "MATERIAL_BUSINESS_IDENTITY_DIFFERS",
            "候选重复Material与Canonical Material存在业务属性差异。",
            differences=differences,
        )


def preview_canonical_material_convergence(*, user) -> dict:
    actor = _actor_context(user)
    materials = {
        row.pk: row for row in Material.objects.filter(
            pk__in=(CANONICAL_MATERIAL_ID, *DUPLICATE_MATERIAL_IDS),
        ).order_by("pk")
    }
    if set(materials) != {CANONICAL_MATERIAL_ID, *DUPLICATE_MATERIAL_IDS}:
        _fail("MATERIAL_SCOPE_INCOMPLETE", "Canonical治理目标Material集合不完整。")
    inventory = material_reference_inventory()
    _validate_scope(materials, inventory)
    return {
        "serviceCode": SERVICE_CODE,
        "databaseBusinessWriteCount": 0,
        "actor": actor,
        "reason": REASON,
        "canonicalMaterial": _snapshot(materials[CANONICAL_MATERIAL_ID]),
        "duplicateMaterials": [
            _snapshot(materials[material_id]) for material_id in DUPLICATE_MATERIAL_IDS
        ],
        "referenceInventory": inventory,
    }


@transaction.atomic
def apply_canonical_material_convergence(*, user) -> dict:
    actor = _actor_context(user)
    materials = {
        row.pk: row for row in Material.objects.select_for_update().filter(
            pk__in=(CANONICAL_MATERIAL_ID, *DUPLICATE_MATERIAL_IDS),
        ).order_by("pk")
    }
    if set(materials) != {CANONICAL_MATERIAL_ID, *DUPLICATE_MATERIAL_IDS}:
        _fail("MATERIAL_SCOPE_INCOMPLETE", "Canonical治理目标Material集合不完整。")
    inventory = material_reference_inventory()
    _validate_scope(materials, inventory)
    inventory_hash = _reference_gate_hash(inventory)
    results = []
    changed = 0
    replayed = 0
    for material_id in DUPLICATE_MATERIAL_IDS:
        material = materials[material_id]
        identity = _source_identity(material)
        request_payload = {
            "serviceCode": SERVICE_CODE,
            "canonicalMaterialId": CANONICAL_MATERIAL_ID,
            "duplicateMaterialId": material_id,
            "targetState": {"is_active": False},
            "reason": REASON,
            "referenceInventoryHash": inventory_hash,
            "sourceIdentityId": identity.pk,
        }
        request_hash = _hash(request_payload)
        key = f"{SERVICE_CODE}:MATERIAL:{material_id}:INACTIVATE"
        ledger = MasterDataWriteRequest.objects.select_for_update().filter(
            organization_id=material.company_id,
            action_code=ACTION_CODE,
            entity_type="materials",
            idempotency_key=key,
        ).first()
        if ledger:
            if (
                ledger.request_hash != request_hash
                or ledger.source_identity_id != identity.pk
                or ledger.target_entity_id != str(material_id)
                or ledger.status != MasterDataWriteRequest.Status.COMMITTED
            ):
                _fail(
                    "IDEMPOTENCY_LEDGER_CONFLICT",
                    "Material停用幂等账本与本次治理合同不一致。",
                    materialId=material_id,
                    ledgerId=ledger.pk,
                )
            audit_id = (ledger.result or {}).get("auditId")
            audit = OrganizationOperatingAuditRecord.objects.filter(
                pk=audit_id,
                action_code=ACTION_CODE,
                target_type="Material",
                target_id=material_id,
                actor=user,
                reason=REASON,
            ).first()
            material.refresh_from_db()
            if material.is_active or not audit:
                _fail(
                    "IDEMPOTENT_RESULT_INCOMPLETE",
                    "Material停用幂等结果缺少停用状态或匹配审计。",
                    materialId=material_id,
                    ledgerId=ledger.pk,
                )
            replayed += 1
            results.append({
                "materialId": material_id,
                "materialCode": material.code,
                "isActive": material.is_active,
                "auditId": audit.pk,
                "actionRequestId": ledger.pk,
                "sourceIdentityId": identity.pk,
                "idempotent": True,
            })
            continue
        if not material.is_active:
            _fail(
                "INACTIVE_WITHOUT_GOVERNANCE_LEDGER",
                "重复Material已停用但缺少本次Canonical治理幂等账本。",
                materialId=material_id,
            )
        ledger = MasterDataWriteRequest.objects.create(
            organization_id=material.company_id,
            action_code=ACTION_CODE,
            entity_type="materials",
            idempotency_key=key,
            request_hash=request_hash,
            source_identity=identity,
            status=MasterDataWriteRequest.Status.RESERVED,
            audit_metadata={
                "serviceCode": SERVICE_CODE,
                "actor": actor,
                "canonicalMaterialId": CANONICAL_MATERIAL_ID,
                "referenceInventoryHash": inventory_hash,
                "historicalRecordPreserved": True,
                "physicalDelete": False,
            },
        )
        result = ProductionFoundationService.save(
            "materials",
            user=user,
            object_id=material_id,
            payload={"is_active": False, "reason": REASON},
            audit_context={
                "serviceCode": SERVICE_CODE,
                "idempotencyKey": key,
                "canonicalMaterialId": CANONICAL_MATERIAL_ID,
                "sourceIdentityId": identity.pk,
                "referenceInventoryHash": inventory_hash,
                "historicalRecordPreserved": True,
                "physicalDelete": False,
            },
        )
        ledger.status = MasterDataWriteRequest.Status.COMMITTED
        ledger.target_entity_id = str(material_id)
        ledger.result = {
            "materialId": material_id,
            "canonicalMaterialId": CANONICAL_MATERIAL_ID,
            "isActive": False,
            "auditId": result["auditId"],
            "sourceIdentityId": identity.pk,
            "referenceInventoryHash": inventory_hash,
            "historicalRecordPreserved": True,
            "physicalDelete": False,
        }
        ledger.save(update_fields=(
            "status", "target_entity_id", "result", "updated_at",
        ))
        changed += 1
        results.append({
            "materialId": material_id,
            "materialCode": material.code,
            "isActive": False,
            "auditId": result["auditId"],
            "actionRequestId": ledger.pk,
            "sourceIdentityId": identity.pk,
            "idempotent": False,
        })

    canonical = Material.objects.get(pk=CANONICAL_MATERIAL_ID)
    duplicates = list(Material.objects.filter(
        pk__in=DUPLICATE_MATERIAL_IDS,
    ).order_by("pk"))
    if not canonical.is_active or any(row.is_active for row in duplicates):
        _fail("CANONICAL_READBACK_FAILED", "Canonical Material停用结果回读失败。")
    return {
        "serviceCode": SERVICE_CODE,
        "idempotent": changed == 0,
        "businessWriteCount": changed * 3,
        "materialWriteCount": changed,
        "auditWriteCount": changed,
        "actionRequestWriteCount": changed,
        "idempotentReplayCount": replayed,
        "actor": actor,
        "reason": REASON,
        "referenceInventoryHash": inventory_hash,
        "canonicalMaterial": _snapshot(canonical),
        "duplicateMaterials": [_snapshot(row) for row in duplicates],
        "results": results,
    }


def readback_canonical_material_convergence(*, user) -> dict:
    actor = _actor_context(user)
    canonical = Material.objects.get(pk=CANONICAL_MATERIAL_ID)
    results = []
    for material_id in DUPLICATE_MATERIAL_IDS:
        material = Material.objects.get(pk=material_id)
        identity = _source_identity(material)
        key = f"{SERVICE_CODE}:MATERIAL:{material_id}:INACTIVATE"
        ledger = MasterDataWriteRequest.objects.filter(
            organization_id=material.company_id,
            action_code=ACTION_CODE,
            entity_type="materials",
            idempotency_key=key,
            status=MasterDataWriteRequest.Status.COMMITTED,
            target_entity_id=str(material_id),
            source_identity=identity,
        ).first()
        audit = OrganizationOperatingAuditRecord.objects.filter(
            pk=(ledger.result or {}).get("auditId") if ledger else None,
            action_code=ACTION_CODE,
            target_type="Material",
            target_id=material_id,
            actor=user,
            reason=REASON,
        ).first()
        if material.is_active or not ledger or not audit:
            _fail(
                "CANONICAL_READBACK_FAILED",
                "重复Material停用状态、幂等账本或审计回读不完整。",
                materialId=material_id,
            )
        results.append({
            "material": _snapshot(material),
            "sourceIdentityId": identity.pk,
            "actionRequestId": ledger.pk,
            "auditId": audit.pk,
            "before": audit.before_snapshot,
            "after": audit.after_snapshot,
        })
    if not canonical.is_active:
        _fail("CANONICAL_MATERIAL_INACTIVE", "Material 130必须保持active。")
    return {
        "serviceCode": SERVICE_CODE,
        "readbackMatch": True,
        "actor": actor,
        "reason": REASON,
        "canonicalMaterial": _snapshot(canonical),
        "duplicates": results,
    }
