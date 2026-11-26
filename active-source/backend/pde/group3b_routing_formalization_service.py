"""Production-authorized, atomic formalization of the frozen Group 3B source."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.master_data_executor_formalization_service import (
    PRE_GROUP3B_RESPONSIBILITY_DESCRIPTION,
    RESPONSIBILITY_CODE,
    RESPONSIBILITY_DESCRIPTION,
    ROLE_CODE,
)
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    Process,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
)

from .manufacturing_structure_service import ManufacturingStructureService
from .models import (
    BOMItem,
    BOMVersion,
    ManufacturingApplicabilityScope,
    ManufacturingProcessType,
    OrderEngineeringInstance,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from .production_foundation_service import (
    ProductionFoundationError,
    ProductionFoundationService,
    _actor_chain,
    _audit,
    _snapshot,
)


VERSION = "GROUP3B-ROUTING-PRODUCTION-FORMALIZATION-V1.0"
SOURCE_PATH = Path(__file__).resolve().parents[1] / "masterdata" / "group3_comparison_source.json"
DECISION_PATH = Path(__file__).resolve().parents[1] / "masterdata" / "group3a_operation_user_decision.json"
EXPECTED_SOURCE_SHA256 = "3CB672466DFF7347CE09696BB4B82AFA3A6B0DDFEABE77ACE36C778B1C13C580"
ROUTING_PERMISSION = "production.master_data.routing.maintain"
EXPECTED_CATEGORIES = {"房门", "柜体", "饰面"}
ACCEPTED_OPERATION_ALIASES = {"拉丝": "拉丝/打磨"}


def _canonical_hash(value):
    return sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def _identity(*, source_system, source_type, object_type, external_id, payload):
    return {
        "sourceSystem": source_system,
        "sourceType": source_type,
        "sourceObjectType": object_type,
        "externalId": external_id,
        "sourceFingerprint": _canonical_hash(payload),
        "auditMetadata": {
            **payload,
            "validation": "USER_VALIDATED",
            "formalizationVersion": VERSION,
        },
    }


def _counts(company_id):
    return {
        "processType": ManufacturingProcessType.objects.filter(company_id=company_id).count(),
        "routing": Routing.objects.filter(company_id=company_id).count(),
        "routingVersion": RoutingVersion.objects.filter(routing__company_id=company_id).count(),
        "routingStep": RoutingStep.objects.filter(routing_version__routing__company_id=company_id).count(),
        "bom": ProductBOM.objects.filter(company_id=company_id).count(),
        "bomVersion": BOMVersion.objects.filter(bom__company_id=company_id).count(),
        "bomItem": BOMItem.objects.filter(bom_version__bom__company_id=company_id).count(),
        "productDefinition": ProductDefinition.objects.filter(company_id=company_id).count(),
        "productVersion": ProductVersion.objects.filter(product__company_id=company_id).count(),
        "orderEngineeringInstance": OrderEngineeringInstance.objects.filter(company_id=company_id).count(),
    }


def _extend_executor_routing_authority(*, admin, executor):
    employee = Employee.objects.select_for_update().select_related("position_ref").get(
        employee_no="EMP047", user=executor, status="active",
    )
    if employee.full_name != "诸葛强" or not employee.position_ref or employee.position_ref.name != "生产总监":
        raise ProductionFoundationError("EXECUTOR_IDENTITY_DRIFT", "EMP047 诸葛强/生产总监执行链已漂移。")
    responsibility = Responsibility.objects.select_for_update().get(code=RESPONSIBILITY_CODE)
    mapping_exists = PositionResponsibility.objects.filter(
        position=employee.position_ref, responsibility=responsibility, active=True,
    ).exists()
    if not mapping_exists or responsibility.status != Responsibility.Status.ACTIVE or not responsibility.is_active:
        raise ProductionFoundationError("EXECUTOR_RESPONSIBILITY_DRIFT", "企业基础资料维护职责链未生效。")
    if responsibility.description not in {
        PRE_GROUP3B_RESPONSIBILITY_DESCRIPTION, RESPONSIBILITY_DESCRIPTION,
    }:
        raise ProductionFoundationError(
            "RESPONSIBILITY_DESCRIPTION_DRIFT", "现有职责说明不属于可受控升级基线。",
        )
    if responsibility.description != RESPONSIBILITY_DESCRIPTION:
        before = {"description": responsibility.description}
        responsibility.description = RESPONSIBILITY_DESCRIPTION
        responsibility.full_clean()
        responsibility.save(update_fields=("description",))
        OrganizationOperatingAuditRecord.objects.create(
            action_code="EXTEND_MASTER_DATA_ROUTING_RESPONSIBILITY",
            actor=admin,
            organization_id=executor.company_id,
            target_type="Responsibility",
            target_id=responsibility.pk,
            target_label=f"{responsibility.code} {responsibility.name}",
            reason="用户独立授权EMP047执行已验收Group 3B Routing正式化",
            before_snapshot={**before, "factSource": "server"},
            after_snapshot={
                "description": responsibility.description,
                "allowedObjects": ["ManufacturingProcessType", "Routing", "RoutingVersion", "RoutingStep"],
                "denied": ["delete", "planning release", "production release", "BOM formalization"],
                "factSource": "server",
            },
        )
    role = Role.objects.select_for_update().get(code=ROLE_CODE)
    permission = Permission.objects.get(code=ROUTING_PERMISSION)
    _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
    if created:
        OrganizationOperatingAuditRecord.objects.create(
            action_code="GRANT_GROUP3B_ROUTING_FORMALIZATION_AUTHORITY",
            actor=admin,
            organization_id=executor.company_id,
            target_type="RolePermission",
            target_id=role.pk,
            target_label=f"{role.code} / {permission.code}",
            reason="仅扩展已验收Routing创建、维护、来源映射与回读权限",
            before_snapshot={"bound": False, "factSource": "server"},
            after_snapshot={"bound": True, "permission": permission.code, "factSource": "server"},
        )
    decision = AuthorizationService.decide(
        user=executor, action_code=ROUTING_PERMISSION,
        organization_id=executor.company_id,
        business_object={"organizationId": executor.company_id},
    )
    if not decision.get("allowed"):
        raise ProductionFoundationError("ROUTING_AUTHORITY_READBACK_FAILED", "Routing最小权限回读失败。")
    return {"permissionCreated": created, "decision": decision}


def _write(entity, *, executor, payload, identity, key):
    return ProductionFoundationService.write(
        entity, user=executor, payload=payload,
        idempotency_key=f"{VERSION}:{key}", source_identity=identity,
    )


def _write_initial_version(*, executor, routing, source_row):
    provenance = {
        "dataProvenance": ["SYSTEM_DERIVED", "INITIAL_FORMALIZATION"],
        "sourceRoutingCode": routing.routing_code,
        "sourceRow": source_row["sourceRow"],
        "sourceFile": source_row["sourceFile"],
        "sourceSha256": EXPECTED_SOURCE_SHA256,
    }
    identity = _identity(
        source_system="PCE_SYSTEM",
        source_type="SYSTEM_DERIVED_INITIAL_FORMALIZATION",
        object_type="ROUTING_VERSION",
        external_id=f"{routing.routing_code}:SYSTEM_INITIAL_VERSION",
        payload=provenance,
    )
    organization_id = executor.company_id
    key = f"{VERSION}:routing-version:{routing.routing_code}:SYSTEM_INITIAL_VERSION"
    request_payload = {
        "routing_id": routing.pk,
        "routing_version": "SYSTEM_INITIAL_VERSION",
        "revision": 1,
        "status": "released",
        "approval_state": "user_validated_initial_formalization",
        "applicability": {},
    }
    request_hash = _canonical_hash({"entity": "routing-versions", "payload": request_payload, "identity": identity})
    lookup = {
        "organization_id": organization_id,
        "source_system": identity["sourceSystem"],
        "source_type": identity["sourceType"],
        "source_object_type": identity["sourceObjectType"],
        "external_id": identity["externalId"],
    }
    source_identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        **lookup,
        defaults={
            "target_entity_type": "routing-versions",
            "mapping_status": ExternalIdentity.MappingStatus.CREATE,
            "source_fingerprint": identity["sourceFingerprint"],
            "audit_metadata": identity["auditMetadata"],
        },
    )
    if source_identity.target_entity_type != "routing-versions":
        raise ProductionFoundationError("SOURCE_IDENTITY_TARGET_CONFLICT", "系统初始版本来源身份类型冲突。")
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=organization_id,
        action_code="production.master_data.create",
        idempotency_key=key,
    ).first()
    if ledger:
        if ledger.request_hash != request_hash:
            raise ProductionFoundationError("IDEMPOTENCY_PAYLOAD_CONFLICT", "系统初始版本幂等内容漂移。")
        if ledger.status == MasterDataWriteRequest.Status.COMMITTED:
            version = RoutingVersion.objects.filter(pk=ledger.target_entity_id, routing=routing).first()
            if not version or version.status != "released":
                raise ProductionFoundationError("IDEMPOTENT_RESULT_DRIFT", "系统初始版本回读与幂等账本不一致。")
            return {"row": _snapshot(version), "idempotentReplay": True, "sourceIdentityId": source_identity.pk}
    else:
        ledger = MasterDataWriteRequest.objects.create(
            organization_id=organization_id,
            action_code="production.master_data.create",
            entity_type="routing-versions",
            idempotency_key=key,
            request_hash=request_hash,
            source_identity=source_identity,
            audit_metadata={"operatorId": executor.pk, **provenance},
        )
    decision = AuthorizationService.decide(
        user=executor, action_code=ROUTING_PERMISSION,
        organization_id=organization_id,
        business_object={"organizationId": organization_id},
    )
    if not decision.get("allowed"):
        raise ProductionFoundationError("PERMISSION_DENIED", "当前执行人无Routing正式化权限。")
    execution_chain = _actor_chain(executor)
    version = RoutingVersion(**request_payload)
    version.full_clean()
    version.save()
    after = _snapshot(version)
    audit = _audit(
        user=executor, organization_id=organization_id,
        action_code=ROUTING_PERMISSION, instance=version,
        before={}, after=after,
        reason="已人工验收来源路线的系统初始版本容器正式化",
        authorization=decision, execution_chain=execution_chain,
    )
    source_identity.target_entity_id = str(version.pk)
    source_identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
    source_identity.source_fingerprint = identity["sourceFingerprint"]
    source_identity.audit_metadata = identity["auditMetadata"]
    source_identity.full_clean()
    source_identity.save()
    result = {"row": after, "auditId": audit.pk, "sourceIdentityId": source_identity.pk, "idempotentReplay": False}
    ledger.status = MasterDataWriteRequest.Status.COMMITTED
    ledger.target_entity_id = str(version.pk)
    ledger.result = result
    ledger.save(update_fields=("status", "target_entity_id", "result", "updated_at"))
    return result


class Group3BRoutingFormalizationService:
    @classmethod
    @transaction.atomic
    def execute(cls, *, admin, executor):
        if not admin or not admin.is_superuser or admin.username != "admin":
            raise ProductionFoundationError("TECHNICAL_ADMIN_REQUIRED", "最小职责扩展必须由正式技术管理员执行。")
        if not executor or executor.username != "emd_emp047" or not executor.is_active:
            raise ProductionFoundationError("FORMAL_EXECUTOR_REQUIRED", "必须使用正式执行人emd_emp047。")
        source_bytes = SOURCE_PATH.read_bytes()
        source_sha = sha256(source_bytes).hexdigest().upper()
        if source_sha != EXPECTED_SOURCE_SHA256:
            raise ProductionFoundationError("TESTED_INPUT_DRIFT", "Group 3B正式来源快照SHA发生漂移。")
        source = json.loads(source_bytes.decode("utf-8"))
        route_rows = source["routingRows"]
        step_rows = source["routingStepRows"]
        scheduling_rows = source["schedulingRows"]
        if (len(route_rows), len(step_rows), len(scheduling_rows)) != (42, 1137, 37):
            raise ProductionFoundationError("FROZEN_SOURCE_COUNT_MISMATCH", "冻结来源数量发生漂移。")
        company_id = executor.company_id
        before = _counts(company_id)
        expected_empty = {"processType": 0, "routing": 0, "routingVersion": 0, "routingStep": 0}
        if any(before[key] != value for key, value in expected_empty.items()):
            expected_complete = {"processType": 14, "routing": 42, "routingVersion": 42, "routingStep": 1137}
            if any(before[key] != value for key, value in expected_complete.items()):
                raise ProductionFoundationError("PARTIAL_FORMALIZATION_BLOCKED", f"生产库存在非预期部分状态：{before}")
        if any(before[key] for key in ("bom", "bomVersion", "bomItem", "productDefinition", "productVersion")):
            raise ProductionFoundationError("PROTECTED_BASELINE_DRIFT", f"受保护制造基线发生漂移：{before}")
        authority = _extend_executor_routing_authority(admin=admin, executor=executor)
        execution_chain = _actor_chain(executor)
        if execution_chain["responsibilityCode"] != RESPONSIBILITY_CODE:
            raise ProductionFoundationError("EXECUTOR_CHAIN_READBACK_FAILED", "正式执行人未解析到企业基础资料维护职责。")

        categories = {
            row.name: row for row in ProductCategory.objects.filter(
                company_id=company_id, name__in=EXPECTED_CATEGORIES, is_active=True,
            )
        }
        if set(categories) != EXPECTED_CATEGORIES:
            raise ProductionFoundationError("CATEGORY_SET_MISMATCH", "房门/柜体/饰面正式分类不完整。")
        operations = {
            row.name: row for row in Process.objects.filter(company_id=company_id, is_active=True)
        }
        if len(operations) != 33:
            raise ProductionFoundationError("OPERATION_COUNT_DRIFT", "正式启用工序数量不是33。")
        resolved_names = {
            ACCEPTED_OPERATION_ALIASES.get(row["operationName"], row["operationName"])
            for row in step_rows
        }
        missing_operations = sorted(resolved_names - set(operations))
        if missing_operations:
            raise ProductionFoundationError("UNRESOLVED_OPERATION", f"来源工序未解析：{missing_operations}")
        decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
        expected_kitting = set(decision["transitionConfiguration"]["kittingOperationNames"])
        actual_kitting = {
            row.name for row in operations.values() if row.default_transition_mode == "KITTING"
        }
        if actual_kitting != expected_kitting:
            raise ProductionFoundationError("OPERATION_TRANSITION_DRIFT", "正式工序GENERAL/KITTING裁决发生漂移。")

        route_rows_by_type = defaultdict(list)
        for row in route_rows:
            category_name = row["applicableProductCategory"]
            if category_name not in EXPECTED_CATEGORIES or not row["routeName"].endswith(category_name):
                raise ProductionFoundationError("ROUTE_IDENTITY_NOT_EXPLAINABLE", row["routeCode"])
            type_code = row["routeCode"].split("/", 1)[0]
            type_name = row["routeName"][:-len(category_name)]
            route_rows_by_type[(type_code, type_name)].append(row)
        if len(route_rows_by_type) != 14 or any(len(rows) != 3 for rows in route_rows_by_type.values()):
            raise ProductionFoundationError("PROCESS_TYPE_DIMENSION_MISMATCH", "14×3工艺类型结构发生漂移。")

        process_types = {}
        for (type_code, type_name), rows in sorted(route_rows_by_type.items()):
            metadata = {
                "sourceFile": rows[0]["sourceFile"],
                "sourceSheet": rows[0]["sourceSheet"],
                "sourceRows": sorted(row["sourceRow"] for row in rows),
                "sourceRoutingCodes": sorted(row["routeCode"] for row in rows),
                "dataProvenance": ["SOURCE", "USER_VALIDATED"],
            }
            result = _write(
                "manufacturing-process-types", executor=executor,
                payload={
                    "company_id": company_id, "code": type_code, "name": type_name,
                    "description": "02工艺路线人工验收来源归并的正式工艺类型",
                    "is_active": True,
                    "reason": "Group 3B已验收14种工艺类型正式化",
                },
                identity=_identity(
                    source_system=rows[0]["sourceFile"], source_type="USER_VALIDATED_XLSX_DERIVED_DIMENSION",
                    object_type="MANUFACTURING_PROCESS_TYPE", external_id=type_code, payload=metadata,
                ),
                key=f"process-type:{type_code}",
            )
            process_types[type_code] = ManufacturingProcessType.objects.get(pk=result["row"]["id"])

        route_steps = defaultdict(list)
        for row in step_rows:
            route_steps[row["routeCode"]].append(row)
        for row in sorted(route_rows, key=lambda item: item["sourceRow"]):
            type_code = row["routeCode"].split("/", 1)[0]
            category = categories[row["applicableProductCategory"]]
            route_metadata = {
                "sourceFile": row["sourceFile"], "sourceSheet": row["sourceSheet"],
                "sourceRow": row["sourceRow"], "routeCode": row["routeCode"],
                "dataProvenance": ["SOURCE", "USER_VALIDATED"],
            }
            route_result = _write(
                "routings", executor=executor,
                payload={
                    "company_id": company_id, "routing_code": row["routeCode"], "name": row["routeName"],
                    "applicability_scope": ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    "product_category_id": category.pk,
                    "manufacturing_process_type_id": process_types[type_code].pk,
                    "status": "released", "is_active": True,
                    "reason": "Group 3B已验收分类级工艺路线正式化",
                },
                identity=_identity(
                    source_system=row["sourceFile"], source_type="USER_VALIDATED_XLSX",
                    object_type="ROUTING", external_id=row["routeCode"], payload=route_metadata,
                ),
                key=f"routing:{row['routeCode']}",
            )
            routing = Routing.objects.get(pk=route_result["row"]["id"])
            version_result = _write_initial_version(executor=executor, routing=routing, source_row=row)
            version = RoutingVersion.objects.get(pk=version_result["row"]["id"])
            for step_row in sorted(route_steps[row["routeCode"]], key=lambda item: item["sequence"]):
                predecessor = step_row.get("predecessorSequence")
                step_metadata = {
                    "sourceFile": step_row["sourceFile"], "sourceSheet": step_row["sourceSheet"],
                    "sourceRow": step_row["sourceRow"], "routeCode": step_row["routeCode"],
                    "sequence": step_row["sequence"], "sourceOperationName": step_row["operationName"],
                    "dataProvenance": ["SOURCE", "USER_VALIDATED"],
                }
                _write(
                    "routing-steps", executor=executor,
                    payload={
                        "routing_version_id": version.pk, "sequence": step_row["sequence"],
                        "operation_id": operations[
                            ACCEPTED_OPERATION_ALIASES.get(step_row["operationName"], step_row["operationName"])
                        ].pk,
                        "predecessor_sequences": [predecessor] if predecessor else [],
                        "effective_transition_mode": None,
                        "instruction": "02工艺路线已人工验收来源步骤",
                        "is_active": True,
                        "reason": "Group 3B已验收工艺路线步骤正式化",
                    },
                    identity=_identity(
                        source_system=step_row["sourceFile"], source_type="USER_VALIDATED_XLSX",
                        object_type="ROUTING_STEP",
                        external_id=f"{step_row['routeCode']}:{step_row['sequence']}",
                        payload=step_metadata,
                    ),
                    key=f"routing-step:{step_row['routeCode']}:{step_row['sequence']}",
                )

        after = _counts(company_id)
        expected_after = {"processType": 14, "routing": 42, "routingVersion": 42, "routingStep": 1137}
        if any(after[key] != value for key, value in expected_after.items()):
            raise ProductionFoundationError("FORMAL_READBACK_FAILED", f"正式化数量回读失败：{after}")
        if any(after[key] for key in ("bom", "bomVersion", "bomItem", "productDefinition", "productVersion")):
            raise ProductionFoundationError("PROTECTED_WRITE_DETECTED", f"检测到禁止写入：{after}")
        if after["orderEngineeringInstance"] != before["orderEngineeringInstance"]:
            raise ProductionFoundationError("ORDER_ENGINEERING_WRITE_DETECTED", "不得创建正式订单工程实例。")

        unique_resolutions = 0
        for row in route_rows:
            type_code = row["routeCode"].split("/", 1)[0]
            result = ManufacturingStructureService.resolve_effective_routing(SimpleNamespace(
                pk=None, company_id=company_id, product_id=None, product=None,
                product_category_id=categories[row["applicableProductCategory"]].pk,
                selected_process_type_id=process_types[type_code].pk,
            ))
            if result["routing"].routing_code != row["routeCode"]:
                raise ProductionFoundationError("EFFECTIVE_ROUTING_DRIFT", row["routeCode"])
            unique_resolutions += 1
        candidate_resolutions = 0
        for row in scheduling_rows:
            type_code = row["sourceEngineeredMaterialName"].split("/", 1)[0]
            category = categories.get(row["sourceProductType"])
            process_type = process_types.get(type_code)
            if not category or not process_type:
                raise ProductionFoundationError("ORDER_ENGINEERED_SOURCE_UNRESOLVED", f"sourceRow={row['sourceRow']}")
            ManufacturingStructureService.resolve_effective_routing(SimpleNamespace(
                pk=None, company_id=company_id, product_id=None, product=None,
                product_category_id=category.pk, selected_process_type_id=process_type.pk,
            ))
            candidate_resolutions += 1

        steps = RoutingStep.objects.filter(routing_version__routing__company_id=company_id).select_related("operation")
        transition_counts = Counter(
            step.effective_transition_mode or step.operation.default_transition_mode for step in steps
        )
        source_alias_count = sum(row["operationName"] == "拉丝" for row in step_rows)
        alias_identity_ids = list(ExternalIdentity.objects.filter(
            organization_id=company_id,
            audit_metadata__formalizationVersion=VERSION,
            audit_metadata__sourceOperationName="拉丝",
            target_entity_type="routing-steps",
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).values_list("target_entity_id", flat=True))
        alias_count = steps.filter(
            pk__in=alias_identity_ids, operation__name="拉丝/打磨",
        ).count()
        if source_alias_count != 3 or alias_count != source_alias_count:
            raise ProductionFoundationError("OPERATION_ALIAS_TRACE_FAILED", "来源拉丝3行未全部指向拉丝/打磨。")
        pinpi_count = steps.filter(operation__name="拼皮").count()
        trace_counts = Counter(ExternalIdentity.objects.filter(
            organization_id=company_id,
            audit_metadata__formalizationVersion=VERSION,
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).values_list("target_entity_type", flat=True))
        return {
            "formalizationVersion": VERSION,
            "sourceSha256": source_sha,
            "executor": execution_chain,
            "authority": authority,
            "before": before,
            "after": after,
            "sourceRouting": 42,
            "sourceRoutingStep": 1137,
            "sourceOrderEngineeredCandidate": 37,
            "routingUniqueResolution": unique_resolutions,
            "orderEngineeredCandidateResolution": candidate_resolutions,
            "traceability": dict(trace_counts),
            "sourceAliasCount": source_alias_count,
            "formalAliasCount": alias_count,
            "autoInsertedPinpi": pinpi_count,
            "transitionCounts": dict(transition_counts),
            "duplicate": 0,
            "unresolved": 0,
        }
