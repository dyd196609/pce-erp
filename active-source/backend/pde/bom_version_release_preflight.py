from pde.baseline_usage_service import production_baselines, production_status
"""Read-only, fail-closed BOMVersion formal-release preflight projection.

This module deliberately does not expose a write operation.  It reports the
persisted business facts and the capabilities of the currently implemented
release path so that the UI cannot confuse a valid BOM with a safe release.
"""

from collections import Counter
from decimal import Decimal
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService

from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    WorkflowInstance,
)

from masterdata.models import ExternalIdentity, MasterDataWriteRequest

from .bom_version_control_service import (
    APPROVED_PROJECTION,
    RELEASE_PERMISSION,
    WORKFLOW_DOCUMENT_TYPES,
    control_chain_readiness,
    eligible_action_actors,
    release_readback,
    workflow_projection,
)

from .models import (
    BOMItemSourceRequirement,
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocumentVersion,
    OrderEngineeringBaseline,
    ProductManufacturingOutput,
)


RELEASE_PERMISSION_CODE = RELEASE_PERMISSION
FINAL_DECISION_BLOCKED = "BLOCKED_BY_EXISTING_WORKFLOW_CONFIGURATION"
BOM_WORKFLOW_DOCUMENT_TYPES = WORKFLOW_DOCUMENT_TYPES
BOM_TRANSITION_OBJECT_TYPES = ("BOMVersion", "pde.BOMVersion", "bom-versions")


def _gate(code, label, passed, evidence, *, required=True):
    if not required:
        status = "NOT_REQUIRED"
    else:
        status = "PASS" if passed else "FAIL"
    return {
        "code": code,
        "label": label,
        "statusCode": status,
        "statusLabel": {
            "PASS": "已满足",
            "FAIL": "未满足",
            "NOT_REQUIRED": "现行规则不要求",
        }[status],
        "evidence": evidence,
    }


def _eligible_release_actors(company_id, bom_version_id):
    return eligible_action_actors(
        company_id, bom_version_id, RELEASE_PERMISSION_CODE,
    )


def _proven_predecessor_calculations(version):
    """Read only complete 0046 authority, never infer lineage from revisions."""
    from .engineering_calculation_continuation_service import (
        EngineeringCalculationContinuationError,
        continuation_proof,
    )
    from .models import EngineeringCalculationContinuation, LegacyInFlightOrderAdoption

    if version.bom_scope != "order_specific" or not version.source_calculation_id:
        return {}, []
    target = version.source_calculation
    cursor = target
    visited = {target.pk}
    ancestors, blockers, path = {}, [], []
    while True:
        row = EngineeringCalculationContinuation.objects.filter(
            new_calculation_id=cursor.pk, status="committed",
        ).select_related("previous_calculation", "new_calculation", "baseline").first()
        if row is None:
            if (not cursor.supersedes_id or LegacyInFlightOrderAdoption.objects.filter(
                    company_id=target.company_id,sales_order_id=target.sales_order_item.sales_order_id).exists()):
                break
            from .formal_engineering_continuation_service import native_successor_proof
            from .engineering_calculation_service import EngineeringCalculationError
            try:
                previous=cursor.supersedes
                proof=native_successor_proof(previous,cursor,company_id=target.company_id,
                    item_id=target.sales_order_item_id,instance_id=version.order_engineering_instance_id)
            except EngineeringCalculationError as error:
                blockers.append({'calculationId':cursor.pk,'code':error.code,'message':error.message})
                break
        else:
            try:
                proof = continuation_proof(row)
            except EngineeringCalculationContinuationError as error:
                blockers.append({"calculationId": cursor.pk, "code": error.code, "message": error.message})
                break
            previous = row.previous_calculation
        exact = (
            previous.pk not in visited
            and cursor.supersedes_id == previous.pk
            and proof.get("newCalculationId") == cursor.pk
            and proof.get("predecessorCalculationId") == previous.pk
            and proof.get("salesOrderItemId") == target.sales_order_item_id
            and proof.get("orderEngineeringInstanceId") == version.order_engineering_instance_id
            and all(
                getattr(previous, name) == getattr(target, name)
                for name in ("company_id", "sales_order_item_id", "engineering_instance_id")
            )
            and previous.engineering_instance_id == version.order_engineering_instance_id
        )
        reference = (previous.trace or {}).get("baselineReference") or {}
        baseline = production_baselines().filter(
            pk=reference.get("id"), company_id=target.company_id,
            sales_order_id=version.order_engineering_instance.sales_order_item.sales_order_id,
            status="confirmed", snapshot_hash=reference.get("snapshotHash"),
        ).first()
        if not exact or baseline is None or not reference.get("snapshotHash"):
            blockers.append({"calculationId": cursor.pk, "code": "BOM_ANCESTOR_SCOPE_UNPROVEN",
                "message": "历史BOM核算、确认基线或接续准确范围未通过。"})
            break
        path = [*path, proof]
        ancestors[previous.pk] = {"calculationId": previous.pk, "baselineId": baseline.pk,
            "baselineSnapshotHash": baseline.snapshot_hash, "continuationProofs": path}
        visited.add(previous.pk)
        cursor = previous
    return ancestors, blockers


def _partition_bom_version_conflicts(version):
    ancestors, lineage_blockers = _proven_predecessor_calculations(version)
    historical, competing = [], []
    for candidate in BOMVersion.objects.filter(bom_id=version.bom_id).exclude(pk=version.pk).order_by("pk"):
        data = {name: getattr(candidate, name) for name in
            ("id", "bom_version", "revision", "status", "effective_date", "expire_date")}
        proof = ancestors.get(candidate.source_calculation_id)
        if (proof and candidate.bom_scope == "order_specific"
                and candidate.order_engineering_instance_id == version.order_engineering_instance_id
                and candidate.status in {"released", "obsolete"}):
            historical.append({**data, **proof})
        else:
            competing.append(data)
    return historical, competing, lineage_blockers


def project_bom_version_release_preflight(version, *, material_details):
    """Project release readiness without mutating any formal or technical data."""

    if version.usage_purpose == 'TEST_BUSINESS':
        return {'decisionCode':'TEST_BUSINESS_PRODUCTION_DENIED','decisionLabel':'测试业务禁止正式评审和发布','releaseAllowed':False,
                'firstBlockerCode':'TEST_BUSINESS_PRODUCTION_DENIED','firstBlockerLabel':'测试草稿仅允许查看和受控复制，不进入正式控制链。',
                'gatePassCount':0,'gateFailCount':1,'gateNotRequiredCount':0,'businessWriteCount':0,
                'gates':[{'code':'TEST_BUSINESS_PRODUCTION_DENIED','statusCode':'FAIL','statusLabel':'测试用途禁止正式发布'}]}
    instance = version.order_engineering_instance
    order_item = instance.sales_order_item
    order = order_item.sales_order
    calculation = version.source_calculation
    company_id = version.bom.company_id

    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    baseline_reference = trace.get("baselineReference") or {}
    baseline_id = baseline_reference.get("id")
    baseline = production_baselines().filter(pk=baseline_id).first()
    confirmed_baselines = list(
        production_baselines().filter(
            company_id=company_id,
            sales_order_id=order.pk,
            status="confirmed",
        ).order_by("-sequence", "-pk")
    )
    current_baseline = confirmed_baselines[0] if confirmed_baselines else None
    baseline_current = bool(
        baseline
        and production_status(baseline) == "confirmed"
        and baseline.company_id == company_id
        and baseline.sales_order_id == order.pk
        and current_baseline
        and current_baseline.pk == baseline.pk
        and baseline.snapshot_hash == baseline_reference.get("snapshotHash")
    )

    calculations = list(
        EngineeringCalculationRecord.objects.filter(
            company_id=company_id,
            engineering_instance_id=instance.pk,
            sales_order_item_id=order_item.pk,
            scope="order_engineering",
        ).order_by("revision", "pk")
    )
    later_calculations = [
        row for row in calculations
        if row.pk != calculation.pk
        and (
            row.revision > calculation.revision
            or row.supersedes_id == calculation.pk
            or row.created_at > calculation.created_at
        )
        and row.status in {"completed", "prepared", "running"}
    ]
    calculation_current = bool(
        calculation.scope == "order_engineering"
        and calculation.status == "completed"
        and calculation.company_id == company_id
        and calculation.engineering_instance_id == instance.pk
        and calculation.sales_order_item_id == order_item.pk
        and not later_calculations
        and int(baseline_reference.get("id") or 0) == int(baseline_id or 0)
    )

    from .material_supply_authority import material_supply_fact
    material_supply_issues = [
        fact for item in version.items.filter(is_active=True).select_related("material")
        if not (fact := material_supply_fact(item.material, item.supply_type))["allowed"]
    ]

    item_ids = [row["bomItemId"] for row in material_details]
    source_rows = list(
        BOMItemSourceRequirement.objects.select_related(
            "bom_item", "material_requirement",
        ).filter(bom_item__bom_version_id=version.pk)
    )
    source_requirement_ids = [row.material_requirement_id for row in source_rows]
    source_per_item = Counter(row.bom_item_id for row in source_rows)
    item_integrity = bool(
        material_details
        and len(item_ids) == len(set(item_ids))
    )
    source_integrity = bool(
        item_integrity
        and source_rows
        and len(source_requirement_ids) == len(set(source_requirement_ids))
        and set(source_per_item) == set(item_ids)
        and all(source_per_item[item_id] > 0 for item_id in item_ids)
        and all(
            row.bom_item.bom_version_id == version.pk
            and row.material_requirement.calculation_id == calculation.pk
            and row.material_requirement.material_id == row.bom_item.material_id
            and row.material_requirement.uom_id == row.bom_item.uom_id
            for row in source_rows
        )
        and all(
            sum(
                (row.contributed_quantity for row in source_rows if row.bom_item_id == item_id),
                Decimal("0"),
            ) == next(
                row.quantity for row in version.items.all() if row.pk == item_id
            )
            for item_id in item_ids
        )
    )

    same_bom_versions = BOMVersion.objects.filter(bom_id=version.bom_id)
    identity_candidate_count = same_bom_versions.filter(
        bom_version=version.bom_version,
    ).count()
    revision_candidate_count = same_bom_versions.filter(revision=version.revision).count()
    historical_versions, competing_versions, lineage_blockers = _partition_bom_version_conflicts(version)
    conflicting_released_versions = [
        row for row in competing_versions if row["status"] == "released"
    ]

    workflow_instances = list(
        WorkflowInstance.objects.filter(
            document_type__in=BOM_WORKFLOW_DOCUMENT_TYPES,
            document_id=version.pk,
        ).values(
            "id", "instance_no", "document_type", "status", "current_step",
            "total_steps", "created_at", "completed_at",
        )
    )
    workflow_ids = [row["id"] for row in workflow_instances]
    approval_tasks = list(
        ApprovalTask.objects.filter(workflow_instance_id__in=workflow_ids)
        .values(
            "id", "task_no", "status", "required_role_code", "minimum_approvals",
            "created_at", "completed_at",
        )
    )
    approval_decisions = list(
        ApprovalDecision.objects.filter(task__workflow_instance_id__in=workflow_ids)
        .values(
            "id", "decision", "actor_id", "actor__username", "actor__real_name",
            "comment", "action_id", "idempotency_key", "created_at", "completed_at",
        )
    )
    transitions = list(
        BusinessStateTransition.objects.filter(
            object_type__in=BOM_TRANSITION_OBJECT_TYPES,
            object_id=version.pk,
        ).values(
            "id", "source_state", "target_state", "action_code",
            "workflow_instance_id", "operator_id", "reason", "audit_reference", "version",
            "timestamp",
        )
    )
    audits = list(
        OrganizationOperatingAuditRecord.objects.filter(
            target_type="BOMVersion", target_id=version.pk,
        ).values("id", "action_code", "actor_id", "reason", "created_at")
    )
    external_identities = list(
        ExternalIdentity.objects.filter(
            target_entity_type__icontains="bom",
            target_entity_id=str(version.pk),
        ).values("id", "source_system", "source_object_type", "external_id", "mapping_status")
    )
    write_requests = list(
        MasterDataWriteRequest.objects.filter(
            entity_type__icontains="bom",
            target_entity_id=str(version.pk),
        ).values("id", "action_code", "idempotency_key", "status")
    )
    eligible_actors = _eligible_release_actors(company_id, version.pk)
    readiness = control_chain_readiness(version)
    approval_projection = workflow_projection(version)
    authoritative_release = release_readback(version)

    document_versions = list(
        EngineeringDocumentVersion.objects.filter(related_bom_id=version.pk)
        .values(
            "id", "document_id", "document_version", "status",
            "order_engineering_baseline_id", "engineering_calculation_id",
            "related_routing_id",
        )
    )
    manufacturing_output_count = ProductManufacturingOutput.objects.filter(
        bom_version_id=version.pk,
    ).count()

    next_state = {
        "draft": "reviewed",
        "reviewed": "released",
        "released": "obsolete",
    }.get(version.status, "")
    current_transition_legal = bool(next_state)
    formal_approval = bool(
        approval_projection["workflow"]
        and approval_projection["workflow"].status == WorkflowInstance.Status.APPROVED
        and len(approval_projection["decisions"]) == 1
        and approval_projection["projectionConsistent"]
        and version.approval_state == APPROVED_PROJECTION
    )
    workflow_ready = readiness["workflowRuntime"]["statusCode"] == "READY"
    sod_ready = readiness["segregationOfDuties"]["statusCode"] == "READY"
    eligibility = FormalManufacturingEligibilityService.resolve(version)
    formal_eligible = eligibility["formalManufacturingEligible"]
    if not formal_eligible:
        decision_code = "BLOCKED_FORMAL_MANUFACTURING_ELIGIBILITY"
        decision_label = "禁止正式制造评审／发布"
        first_blocker = {"code": eligibility["decisionCode"], "message": eligibility["message"]}
        minimum_remediation = "保持当前草稿只读；开发测试草稿不取得正式评审、发布或制造资格。"
    elif not workflow_ready:
        decision_code = "BLOCKED_BY_EXISTING_WORKFLOW_CONFIGURATION"
        decision_label = "控制链已接入，现有Workflow配置阻断"
        first_blocker = readiness["workflowRuntime"]["blocker"]
        minimum_remediation = "只需在正式配置流程中建立一个适用于BOMVersion的单节点评审模板；本轮不得写入。"
    elif not sod_ready:
        decision_code = "CONTROL_CHAIN_READY_BUT_ACTOR_ASSIGNMENT_REQUIRED"
        decision_label = "控制链已就绪，仍需不同评审人与发布人"
        first_blocker = {
            "code": readiness["segregationOfDuties"]["blockerCode"],
            "message": "正式库缺少一组满足评审人与发布人不同的合法人员组合。",
        }
        minimum_remediation = "只补充一名具备现有正式资格且与另一动作人员不同的业务人员。"
    elif (
        version.status == "released"
        and formal_approval
        and authoritative_release["released"]
    ):
        decision_code = "PASS_FORMAL_RELEASE_COMPLETE"
        decision_label = "正式发布已完成"
        first_blocker = {
            "code": "FORMAL_RELEASE_ALREADY_COMPLETED",
            "message": f"{version.bom_version}已完成正式发布；相同BOM版本不得重复发布。",
        }
        minimum_remediation = "本节点已闭环；后续仅可按独立授权进入工艺路线管理。"
    elif version.status == "reviewed" and formal_approval:
        decision_code = "PASS_FORMAL_REVIEW_COMPLETE_READY_FOR_EXPLICIT_RELEASE"
        decision_label = "正式评审已完成，发布保持未执行"
        first_blocker = {
            "code": "EXPLICIT_RELEASE_AUTHORIZATION_REQUIRED",
            "message": f"{version.bom_version}已完成正式评审；发布必须由独立发布身份在本页明确执行。",
        }
        minimum_remediation = "由服务端解析出的正式发布人通过受控发布服务执行reviewed → released。"
    else:
        decision_code = "PASS_CONTROL_CHAIN_READY_FOR_FORMAL_REVIEW"
        decision_label = "控制链已就绪，等待正式评审授权"
        first_blocker = {
            "code": "FORMAL_REVIEW_NOT_EXECUTED",
            "message": f"本轮未执行正式评审；{version.bom_version}当前为{version.status} / {version.approval_state}。",
        }
        minimum_remediation = "下一独立主题仅可发起并执行draft → reviewed正式评审。"
    software_gaps = []
    configuration_gaps = [
        readiness["workflowRuntime"]["blocker"]
    ] if not workflow_ready else []
    gates = [
        _gate("IDENTITY_UNIQUE", f"{version.bom_version}正式身份唯一", identity_candidate_count == 1, f"BOMVersion ID {version.pk}；身份候选 {identity_candidate_count}。"),
        _gate("BOM_REVISION_UNIQUE", "ProductBOM内Revision唯一", revision_candidate_count == 1, f"Revision {version.revision}候选 {revision_candidate_count}。"),
        _gate("FORMAL_SCOPE_CONSISTENT", "Company/订单行/OEI/核算归属一致", bool(version.bom_id and version.bom.company_id == instance.company_id == order.company_id and instance.sales_order_item_id == order_item.pk and calculation.engineering_instance_id == instance.pk), f"COMP{company_id:03d} / {order.order_no} 行{order_item.line_no} / {instance.instance_no} / {calculation.calculation_no}。"),
        _gate("BASELINE_CURRENT", "当前正式工程基线一致", baseline_current, f"{baseline.baseline_no if baseline else '未解析'}；confirmed候选 {len(confirmed_baselines)}。"),
        _gate("CALCULATION_CURRENT", "来源工程核算完成且未被替代", calculation_current, f"{calculation.calculation_no} rev{calculation.revision} / {calculation.status}；后续候选 {len(later_calculations)}。"),
        _gate("BOM_ITEMS_COMPLETE", f"BOMItem完整（当前{len(material_details)}项）", item_integrity, f"读取 {len(material_details)} 项；BOMItem身份唯一。"),
        _gate("MATERIAL_SUPPLY_QUALIFIED", "BOM供给方式与正式物料资格一致", not material_supply_issues, "；".join(issue["message"] for issue in material_supply_issues) or "明确MAKE/BUY均符合现有物料供给事实。"),
        _gate("SOURCE_REQUIREMENTS_COMPLETE", f"Requirement来源完整（当前{len(source_rows)}条）", source_integrity, f"读取 {len(source_rows)} 条；唯一Requirement {len(set(source_requirement_ids))} 条。"),
        _gate("NO_COMPETING_VERSION", "无同ProductBOM竞争版本", not competing_versions, f"其他版本 {len(competing_versions)} 个。"),
        _gate("NO_RELEASED_VERSION_CONFLICT", "无冲突已发布版本", not conflicting_released_versions, f"冲突已发布版本 {len(conflicting_released_versions)} 个。"),
        _gate("RELEASE_PERMISSION_ACTOR", "存在COMP001范围合法执行人员", bool(eligible_actors), f"非superuser合法执行身份 {len(eligible_actors)} 个。"),
        _gate("CURRENT_TRANSITION_LEGAL", "当前状态具备唯一合法下一动作", current_transition_legal, f"当前{version.status}；合法下一状态为{next_state or '无'}；draft直接released始终禁止。"),
        _gate(
            "FORMAL_APPROVAL",
            "正式评审/审批事实已形成并被发布服务强制校验",
            formal_approval,
            (
                f"approval_state={version.approval_state}；BOM Workflow {len(workflow_instances)}；"
                f"approved决定 {len(approval_projection['decisions'])}；"
                + ("正式评审事实唯一且投影一致。" if formal_approval else "正式评审尚未完成。")
            ),
        ),
        _gate(
            "BUSINESS_STATE_TRANSITION",
            "统一BusinessStateTransition已接入正式服务",
            True,
            f"控制服务已强制调用统一transition_business_object；{version.bom_version}当前正式状态迁移 {len(transitions)} 条。",
        ),
        _gate(
            "IDEMPOTENT_RELEASE",
            "评审/发布动作具备请求身份与安全幂等账本",
            True,
            f"控制服务强制Idempotency-Key并复用ExternalIdentity + MasterDataWriteRequest；{version.bom_version}当前账本 {len(external_identities)} / {len(write_requests)}。",
        ),
        _gate("WORKFLOW_RUNTIME_CONFIGURATION", "现有Workflow Runtime具备适用BOMVersion模板", workflow_ready, readiness["workflowRuntime"]["blocker"].get("message", "已唯一解析正式BOMVersion评审模板。")),
        _gate("SEGREGATION_OF_DUTIES", "评审人与发布人可执行最小职责分离", sod_ready, f"合法评审候选 {len(readiness['segregationOfDuties']['reviewActors'])}；合法发布候选 {len(readiness['segregationOfDuties']['releaseActors'])}；不同人员组合 {readiness['segregationOfDuties']['separatedActorPairCount']}。"),
        _gate("EFFECTIVE_DATE", "发布必须提供生效日期", True, "现行BOMVersion模型与transition未把effective_date设为发布必填。", required=False),
        _gate("RELEASE_REASON", "发布必须提供发布说明", True, "统一控制服务强制非空reason，并写入BST与Audit。"),
        _gate("SIDE_EFFECTS_DISCLOSED", "发布自动副作用已明确", True, "受控动作只写Workflow、BOMVersion投影、BusinessStateTransition、Audit与请求账本；不自动改ProductBOM、资料、制造输出、MRP、采购/生产需求、ECN或Routing。"),
        _gate("NO_DOCUMENT_CYCLE", "BOM与工程资料发布无循环依赖", True, f"BOM transition不读取资料状态；关联资料版本 {len(document_versions)} 个，资料发布校验也不要求BOM已released。"),
    ]

    if not formal_eligible:
        gates.insert(0, _gate("FORMAL_MANUFACTURING_ELIGIBILITY", "正式制造用途资格", False,
                              eligibility["message"]))
    return {
        "decisionCode": decision_code,
        "decisionLabel": decision_label,
        "releaseAllowed": bool(
            formal_eligible and version.status == "reviewed"
            and formal_approval
            and readiness["formalExecutionReady"]
        ),
        "explicitReleaseAuthorizationAcceptable": bool(
            formal_eligible and version.status == "reviewed"
            and formal_approval
            and readiness["formalExecutionReady"]
        ),
        "firstBlockerCode": first_blocker.get("code", ""),
        "firstBlockerLabel": first_blocker.get("message", ""),
        "minimumRemediation": minimum_remediation,
        "stateMachine": {
            "legalStates": ["draft", "reviewed", "released", "obsolete"],
            "legalTransitions": ["draft → reviewed", "reviewed → released", "released → obsolete"],
            "currentStateCode": version.status,
            "currentStateLabel": version.get_status_display(),
            "nextLegalStateCode": next_state,
            "directDraftToReleasedAllowed": False,
            "effectiveStateIsSeparate": False,
        },
        "permission": {
            "code": RELEASE_PERMISSION_CODE,
            "organizationId": company_id,
            "eligibleActors": eligible_actors,
            "eligibleActorCount": len(eligible_actors),
            "superuserExcludedFromBusinessEvidence": True,
        },
        "approval": {
            "projectionState": version.approval_state,
            "authoritativeProjectionState": approval_projection["projectionState"],
            "projectionConsistent": approval_projection["projectionConsistent"],
            "workflowInstances": workflow_instances,
            "approvalTasks": approval_tasks,
            "approvalDecisions": approval_decisions,
            "formallyEnforcedByReleaseService": True,
            "separationOfDutiesEnforced": True,
        },
        "controlChainReadiness": readiness,
        "releaseControl": {
            "api": "POST /api/pde/a1-engineering/bom-versions/<id>/transition/",
            "service": "EngineeringLifecycleService.transition",
            "dedicatedBomReleaseApi": False,
            "requiredTargetFromCurrentState": "reviewed",
            "businessStateTransitions": transitions,
            "businessAudits": audits,
            "externalIdentities": external_identities,
            "writeRequests": write_requests,
            "businessAuditImplemented": True,
            "businessStateTransitionEnforced": True,
            "workflowApprovalEnforced": True,
            "requestIdentityRequired": True,
            "idempotencyLedgerImplemented": True,
            "repeatReleasedCallReturnsIdempotentReadback": True,
            "releaseActorFieldExists": False,
            "releaseTimestampFieldExists": False,
            "authoritativeReleaseReadback": authoritative_release,
            "effectiveDateRequired": False,
            "releaseReasonRequired": True,
        },
        "baseline": {
            "id": baseline.pk if baseline else None,
            "baselineNo": baseline.baseline_no if baseline else "",
            "statusCode": baseline.status if baseline else "",
            "statusLabel": baseline.get_status_display() if baseline else "未解析",
            "snapshotHash": baseline.snapshot_hash if baseline else "",
            "isCurrent": baseline_current,
            "confirmedCandidateCount": len(confirmed_baselines),
        },
        "calculation": {
            "id": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "revision": calculation.revision,
            "statusCode": calculation.status,
            "statusLabel": calculation.get_status_display(),
            "isCurrent": calculation_current,
            "laterCandidateCount": len(later_calculations),
        },
        "versionConflicts": {
            "identityCandidateCount": identity_candidate_count,
            "revisionCandidateCount": revision_candidate_count,
            "competingVersions": competing_versions,
            "conflictingReleasedVersions": conflicting_released_versions,
            "provenHistoricalVersions": historical_versions,
            "lineageBlockers": lineage_blockers,
        },
        "documentDependency": {
            "versions": document_versions,
            "blocksBomRelease": False,
            "cycleDetected": False,
        },
        "downstreamEffects": {
            "productBomStatusMutation": False,
            "oldBomVersionAutoObsolete": False,
            "currentVersionAutoSelection": False,
            "engineeringDocumentMutation": False,
            "manufacturingOutputCreation": False,
            "mrpEntry": False,
            "purchaseDemandCreation": False,
            "productionDemandCreation": False,
            "ecnCreation": False,
            "routingMutation": False,
            "organizationOperatingAuditCreation": True,
            "currentManufacturingOutputCount": manufacturing_output_count,
        },
        "softwareGaps": software_gaps,
        "configurationGaps": configuration_gaps,
        "gates": gates,
        "gatePassCount": sum(1 for gate in gates if gate["statusCode"] == "PASS"),
        "gateFailCount": sum(1 for gate in gates if gate["statusCode"] == "FAIL"),
        "gateNotRequiredCount": sum(1 for gate in gates if gate["statusCode"] == "NOT_REQUIRED"),
        "businessWriteCount": 0,
    }
