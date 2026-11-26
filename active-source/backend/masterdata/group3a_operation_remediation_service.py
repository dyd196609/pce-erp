"""User-authorized, narrowly scoped Group 3A operation remediation."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from django.db import transaction

from masterdata.group3_comparison_runtime import _source
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from masterdata.validated_fact_formalization_service import _bind_existing
from pde.models import BOMItem, BOMVersion, ProductBOM, Routing, RoutingStep, RoutingVersion
from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService, _actor_chain
from system.models import Process


VERSION = "GROUP3A-OPERATION-TARGETED-REMEDIATION-V2"
PINPI_NAME = "拼皮"
ALIAS_SOURCE_VALUE = "拉丝"
ALIAS_FORMAL_NAME = "拉丝/打磨"
TRANSITION_UPDATE_ACTION = "production.master_data.resource.maintain"
DECISION_PATH = Path(__file__).with_name("group3a_operation_user_decision.json")


def _decision():
    with DECISION_PATH.open(encoding="utf-8") as decision_handle:
        return json.load(decision_handle)


def _norm(value):
    return "".join(str(value or "").casefold().split())


def _protected_counts(company_id):
    return {
        "boms": ProductBOM.objects.filter(company_id=company_id).count(),
        "bomVersions": BOMVersion.objects.filter(bom__company_id=company_id).count(),
        "bomItems": BOMItem.objects.filter(bom_version__bom__company_id=company_id).count(),
        "routings": Routing.objects.filter(company_id=company_id).count(),
        "routingVersions": RoutingVersion.objects.filter(routing__company_id=company_id).count(),
        "routingSteps": RoutingStep.objects.filter(routing_version__routing__company_id=company_id).count(),
    }


def _pinpi_identity():
    decision = {
        "operationName": PINPI_NAME,
        "sequenceSemantic": ["开料", "拼皮", "后续工序由RoutingStep决定"],
        "validation": "USER_VALIDATED_REAL_OPERATION",
        "version": VERSION,
    }
    return {
        "sourceSystem": "GROUP3A_USER_VALIDATED_DECISION",
        "sourceType": "USER_VALIDATED_DECISION",
        "sourceObjectType": "OPERATION",
        "externalId": "GROUP3A:OPERATION:拼皮",
        "sourceFingerprint": sha256(json.dumps(decision, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "auditMetadata": decision,
    }


def _alias_identity(source):
    occurrences = [
        {
            "sourceRow": row["sourceRow"],
            "routeCode": row["routeCode"],
            "sequence": row["sequence"],
        }
        for row in source["routingStepRows"]
        if row["operationName"] == ALIAS_SOURCE_VALUE
    ]
    metadata = {
        "sourceFile": "02工艺路线.xlsx",
        "sourceSheet": "工艺路线",
        "sourceValue": ALIAS_SOURCE_VALUE,
        "formalName": ALIAS_FORMAL_NAME,
        "occurrences": occurrences,
        "validation": "USER_VALIDATED_ALIAS",
        "formalizationVersion": VERSION,
    }
    return {
        "sourceSystem": "02工艺路线.xlsx",
        "sourceType": "USER_VALIDATED_ALIAS",
        "sourceObjectType": "ROUTING_STEP_OPERATION_VALUE",
        "externalId": ALIAS_SOURCE_VALUE,
        "sourceFingerprint": sha256(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "auditMetadata": metadata,
    }


def _find_unique_operation(company_id, name):
    matches = [row for row in Process.objects.filter(company_id=company_id) if _norm(row.name) == _norm(name)]
    if len(matches) > 1:
        raise ProductionFoundationError("DUPLICATE_OPERATION_NAME", f"正式库存在重复工序：{name}")
    return matches[0] if matches else None


def _bind_or_replay(*, user, company_id, entity, identity, instance, reason, execution_chain):
    existing = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system=identity["sourceSystem"],
        source_type=identity["sourceType"],
        source_object_type=identity["sourceObjectType"],
        external_id=identity["externalId"],
    ).first()
    if existing and existing.mapping_status == ExternalIdentity.MappingStatus.MATCH:
        if existing.target_entity_type != entity or existing.target_entity_id != str(instance.pk):
            raise ProductionFoundationError("SOURCE_IDENTITY_TARGET_CONFLICT", "来源身份已绑定其他正式对象。")
        return {"matchedExisting": True, "created": False, "targetId": instance.pk, "sourceIdentityId": existing.pk, "idempotentReplay": True}
    result = _bind_existing(
        user=user, company_id=company_id, entity=entity, identity=identity,
        instance=instance, reason=reason, execution_chain=execution_chain,
    )
    bound = ExternalIdentity.objects.get(
        organization_id=company_id,
        source_system=identity["sourceSystem"],
        source_type=identity["sourceType"],
        source_object_type=identity["sourceObjectType"],
        external_id=identity["externalId"],
    )
    return {**result, "sourceIdentityId": bound.pk, "idempotentReplay": False}


@transaction.atomic
def apply_operation_transition_decision(
    user, *, exact_name, target_mode, idempotency_key, reason,
):
    """Apply one exact, user-validated Operation default-transition decision."""
    company_id = int(user.company_id or 0)
    if not company_id:
        raise ProductionFoundationError("ORGANIZATION_REQUIRED", "执行人必须属于正式公司。")
    exact_name = str(exact_name or "").strip()
    if not exact_name:
        raise ProductionFoundationError("OPERATION_NAME_REQUIRED", "必须提供工序精确名称。")
    if target_mode not in Process.TransitionMode.values:
        raise ProductionFoundationError("TRANSITION_MODE_INVALID", "目标转序方式无效。")
    key = str(idempotency_key or "").strip()
    if not key:
        raise ProductionFoundationError("IDEMPOTENCY_KEY_REQUIRED", "正式更新必须提供幂等键。")

    matches = list(Process.objects.select_for_update().filter(
        company_id=company_id, name=exact_name,
    ))
    if len(matches) != 1:
        code = "OPERATION_NOT_FOUND" if not matches else "DUPLICATE_OPERATION_NAME"
        raise ProductionFoundationError(code, f"正式工序精确匹配数量必须为1：{exact_name}")
    operation = matches[0]
    identity = ExternalIdentity.objects.filter(
        organization_id=company_id,
        target_entity_type="operations",
        target_entity_id=str(operation.pk),
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).order_by("pk").first()
    if not identity:
        raise ProductionFoundationError("SOURCE_IDENTITY_REQUIRED", "正式工序缺少已匹配来源身份。")

    request_payload = {
        "entity": "operations",
        "objectId": operation.pk,
        "exactName": exact_name,
        "targetMode": target_mode,
        "reason": reason,
        "dataProvenance": ["REAL", "USER_VALIDATED"],
    }
    request_hash = sha256(json.dumps(
        request_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=company_id,
        action_code=TRANSITION_UPDATE_ACTION,
        idempotency_key=key,
    ).first()
    if ledger and ledger.request_hash != request_hash:
        raise ProductionFoundationError(
            "IDEMPOTENCY_PAYLOAD_CONFLICT", "同一幂等键不得提交不同的工序裁决。"
        )
    if ledger and ledger.status == MasterDataWriteRequest.Status.COMMITTED:
        operation.refresh_from_db()
        if operation.default_transition_mode != target_mode:
            raise ProductionFoundationError("IDEMPOTENT_RESULT_DRIFT", "幂等账本与正式工序回读不一致。")
        return {**ledger.result, "idempotentReplay": True}
    if ledger is None:
        ledger = MasterDataWriteRequest.objects.create(
            organization_id=company_id,
            action_code=TRANSITION_UPDATE_ACTION,
            entity_type="operations",
            idempotency_key=key,
            request_hash=request_hash,
            source_identity=identity,
            audit_metadata={
                "operatorId": user.pk,
                "dataProvenance": ["REAL", "USER_VALIDATED"],
                "decisionScope": "OPERATION_DEFAULT_TRANSITION_MODE",
            },
        )

    previous_mode = operation.default_transition_mode
    result = ProductionFoundationService.save(
        "operations", user=user, object_id=operation.pk,
        payload={"default_transition_mode": target_mode, "reason": reason},
    )
    operation.refresh_from_db()
    if operation.default_transition_mode != target_mode:
        raise ProductionFoundationError("FORMAL_READBACK_FAILED", "正式工序转序方式回读不一致。")
    committed = {
        **result,
        "idempotentReplay": False,
        "previousMode": previous_mode,
        "currentMode": operation.default_transition_mode,
        "dataProvenance": ["REAL", "USER_VALIDATED"],
    }
    ledger.status = MasterDataWriteRequest.Status.COMMITTED
    ledger.target_entity_id = str(operation.pk)
    ledger.result = committed
    ledger.save(update_fields=("status", "target_entity_id", "result", "updated_at"))
    return committed


@transaction.atomic
def apply_group3a_operation_remediation(user):
    company_id = int(user.company_id or 0)
    if not company_id:
        raise ProductionFoundationError("ORGANIZATION_REQUIRED", "执行人必须属于正式公司。")
    source = _source()
    decision = _decision()
    kitting_names = set(decision["transitionConfiguration"]["kittingOperationNames"])
    protected_before = _protected_counts(company_id)
    operation_before = Process.objects.filter(company_id=company_id).count()
    execution_chain = _actor_chain(user)

    pinpi = _find_unique_operation(company_id, PINPI_NAME)
    if pinpi:
        pinpi_result = _bind_or_replay(
            user=user, company_id=company_id, entity="operations",
            identity=_pinpi_identity(), instance=pinpi,
            reason="用户确认拼皮为真实生产工序；匹配现有正式工序。",
            execution_chain=execution_chain,
        )
        pinpi_state = "MATCHED"
    else:
        pinpi_result = ProductionFoundationService.write(
            "operations", user=user,
            payload={
                "company_id": company_id,
                "name": PINPI_NAME,
                "operation_kind": Process.OperationKind.ATOMIC,
                "calculation_basis": Process.CalculationBasis.UNDETERMINED,
                "default_transition_mode": Process.TransitionMode.GENERAL,
                "is_active": True,
                "reason": "用户确认拼皮为企业真实生产工序；具体顺序由未来RoutingStep决定。",
            },
            idempotency_key=f"{VERSION}:CREATE:拼皮",
            source_identity=_pinpi_identity(),
        )
        pinpi = Process.objects.get(pk=pinpi_result["row"]["id"])
        pinpi_state = "MATCHED" if pinpi_result.get("idempotentReplay") else "CREATED"

    transition_update_count = 0
    transition_audit_ids = []
    for operation in Process.objects.filter(company_id=company_id).order_by("code", "id"):
        desired = Process.TransitionMode.KITTING if operation.name in kitting_names else Process.TransitionMode.GENERAL
        if operation.default_transition_mode == desired:
            continue
        result = ProductionFoundationService.save(
            "operations", user=user, object_id=operation.pk,
            payload={
                "default_transition_mode": desired,
                "reason": "GROUP3A用户确认：白坯检验、成品检为齐套工序，其余当前工序为一般工序。",
            },
        )
        transition_update_count += 1
        transition_audit_ids.append(result["auditId"])

    alias_target = _find_unique_operation(company_id, ALIAS_FORMAL_NAME)
    if not alias_target:
        raise ProductionFoundationError("ALIAS_TARGET_NOT_FOUND", "正式工序‘拉丝/打磨’不存在。")
    alias_identity = _alias_identity(source)
    alias_result = _bind_or_replay(
        user=user, company_id=company_id, entity="operations",
        identity=alias_identity, instance=alias_target,
        reason="用户确认来源‘拉丝’与正式‘拉丝/打磨’为同一工序。",
        execution_chain=execution_chain,
    )

    protected_after = _protected_counts(company_id)
    if protected_before != protected_after:
        raise ProductionFoundationError("PROTECTED_SCOPE_WRITE_DETECTED", "检测到BOM或Routing范围发生变化，事务已回滚。")

    operations = list(Process.objects.filter(company_id=company_id).order_by("display_order", "id"))
    alias_occurrences = alias_identity["auditMetadata"]["occurrences"]
    return {
        "version": VERSION,
        "group3aOperation": "REMEDIATION_COMPLETE",
        "userValidated": "AWAITING_TARGETED_RECHECK",
        "operationCountBefore": operation_before,
        "operationCountAfter": len(operations),
        "pinpi": {
            "status": pinpi_state,
            "id": pinpi.pk,
            "code": pinpi.code,
            "name": pinpi.name,
            "sourceIdentityId": pinpi_result.get("sourceIdentityId"),
        },
        "transitionConfiguration": {
            "kittingCount": sum(row.default_transition_mode == Process.TransitionMode.KITTING for row in operations),
            "generalCount": sum(row.default_transition_mode == Process.TransitionMode.GENERAL for row in operations),
            "kittingNames": [row.name for row in operations if row.default_transition_mode == Process.TransitionMode.KITTING],
            "updatedCount": transition_update_count,
            "auditIds": transition_audit_ids,
        },
        "alias": {
            "sourceValue": ALIAS_SOURCE_VALUE,
            "formalName": alias_target.name,
            "formalCode": alias_target.code,
            "sourceOccurrenceCount": len(alias_occurrences),
            "resolvedOccurrenceCount": len(alias_occurrences),
            "sourceIdentityId": alias_result.get("sourceIdentityId"),
            "occurrences": alias_occurrences,
        },
        "protectedWrites": {
            "before": protected_before,
            "after": protected_after,
            "writeCount": 0,
        },
        "executionChain": execution_chain,
    }


def build_group3a_operation_revalidation(company_id):
    source = _source()
    operations = list(
        Process.objects.filter(company_id=company_id)
        .select_related("calculation_uom")
        .order_by("display_order", "id")
    )
    by_name = {row.name: row for row in operations}
    opening = by_name.get("开料")
    final_target = by_name.get("试装")
    pinpi = by_name.get(PINPI_NAME)
    alias_identity = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system="02工艺路线.xlsx",
        source_type="USER_VALIDATED_ALIAS",
        source_object_type="ROUTING_STEP_OPERATION_VALUE",
        external_id=ALIAS_SOURCE_VALUE,
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).first()
    alias_occurrences = [row for row in source["routingStepRows"] if row["operationName"] == ALIAS_SOURCE_VALUE]
    pinpi_identity = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system="GROUP3A_USER_VALIDATED_DECISION",
        source_type="USER_VALIDATED_DECISION",
        source_object_type="OPERATION",
        external_id="GROUP3A:OPERATION:拼皮",
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).first()
    pinpi_created = bool(pinpi_identity and MasterDataWriteRequest.objects.filter(
        source_identity=pinpi_identity,
        action_code="production.master_data.create",
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).exists())

    def operation_row(operation, acceptance_focus):
        uom = "待确认 / 来源未提供"
        if operation.calculation_uom_id:
            symbol = operation.calculation_uom.symbol or operation.calculation_uom.code
            uom = f"{operation.calculation_uom.name}（{symbol}）" if symbol else operation.calculation_uom.name
        return {
            "displayOrder": operation.display_order,
            "operationCode": operation.code,
            "operationName": operation.name,
            "calculationMethod": {
                "count": "按数量", "length": "按长度", "area": "按面积",
                "volume": "按体积", "mass": "按质量", "time": "按时间",
                "other": "其它", "undetermined": "待确认",
            }.get(operation.calculation_basis, "待确认"),
            "calculationUom": uom,
            "transitionMode": "齐套工序" if operation.default_transition_mode == "KITTING" else "一般工序",
            "enabledLabel": "启用" if operation.is_active else "停用",
            "source": "用户确认 / 正式Process回读" if operation.name == PINPI_NAME else "01工序.xlsx / 正式Process回读",
            "acceptanceStatus": "等待定向复验",
            "acceptanceFocus": acceptance_focus,
        }

    focus_rows = []
    if final_target:
        focus_rows.append(operation_row(final_target, "唯一待确认项：试装 = 齐套工序"))

    alias_target_resolved = bool(
        alias_identity and by_name.get(ALIAS_FORMAL_NAME)
        and alias_identity.target_entity_id == str(by_name[ALIAS_FORMAL_NAME].pk)
    )
    general_rows = [row.name for row in operations if row.default_transition_mode == "GENERAL"]
    kitting_rows = [row.name for row in operations if row.default_transition_mode == "KITTING"]
    return {
        "version": VERSION,
        "readOnly": True,
        "group3aOperation": "REMEDIATION_COMPLETE",
        "userValidated": "AWAITING_TARGETED_RECHECK",
        "formalOperationCount": len(operations),
        "finalTarget": {
            "operationId": final_target.pk if final_target else None,
            "operationCode": final_target.code if final_target else "",
            "operationName": final_target.name if final_target else "",
            "transitionMode": (
                "齐套工序" if final_target and final_target.default_transition_mode == "KITTING"
                else "一般工序" if final_target else "缺失"
            ),
            "transitionModeCode": final_target.default_transition_mode if final_target else "",
            "dataProvenance": ["REAL", "USER_VALIDATED"] if final_target else [],
            "readbackPassed": bool(
                final_target and final_target.default_transition_mode == Process.TransitionMode.KITTING
            ),
        },
        "pinpi": {
            "status": ("CREATED" if pinpi_created else "MATCHED") if pinpi else "MISSING",
            "operationCode": pinpi.code if pinpi else "",
            "displayOrder": pinpi.display_order if pinpi else None,
            "openingDisplayOrder": opening.display_order if opening else None,
            "displayOrderVerified": bool(
                opening and pinpi and opening.display_order == 1 and pinpi.display_order == 2
            ),
            "sequencePreview": ["开料", "拼皮", "后续工序由具体RoutingStep决定"],
        },
        "kitting": {"count": len(kitting_rows), "names": kitting_rows},
        "general": {"count": len(general_rows), "names": general_rows},
        "alias": {
            "sourceValue": ALIAS_SOURCE_VALUE,
            "formalName": ALIAS_FORMAL_NAME,
            "sourceOccurrenceCount": len(alias_occurrences),
            "resolvedOccurrenceCount": len(alias_occurrences) if alias_target_resolved else 0,
            "statusLabel": "3/3 已解析" if alias_target_resolved else "待整改",
            "occurrences": [
                {"routeCode": row["routeCode"], "routeName": row["routeName"], "sequence": row["sequence"], "statusLabel": "已映射至拉丝/打磨" if alias_target_resolved else "未解析"}
                for row in alias_occurrences
            ],
        },
        "focusRows": focus_rows,
        "calculationBasisColumn": "READY",
        "calculationUomColumn": "READY",
        "bomRoutingStepWriteCount": 0,
        "group4Entered": False,
        "planningProductionDeployed": False,
    }
