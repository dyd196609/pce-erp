"""Formal RoutingVersion review on the shared PCE workflow ledgers.

This module deliberately owns only the ``draft -> reviewed`` review action.
It reuses the existing Workflow Runtime, BusinessStateTransition, audit and
idempotency ledgers.  It never publishes a routing version and it never creates
workflow configuration, permissions, roles, users or scope assignments.
"""

from __future__ import annotations

from hashlib import sha256
import json

from django.db import transaction
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
)
from workflow_runtime.state_transitions import transition_business_object

from .models import RoutingVersion
from .routing_manual_applicability_service import exact_contexts_for_version
from .routing_step_applicability_service import RoutingStepApplicabilityResolver
from .routing_version_integrity import content_hash, routing_version_content_snapshot
from .routing_version_workflow_catalog import CANONICAL_DEFINITION


CONTROL_CONTRACT = "PCE-ROUTING-VERSION-FORMAL-REVIEW-V1.0"
DOCUMENT_TYPE = "RoutingVersion"
WORKFLOW_DOCUMENT_TYPES = (
    DOCUMENT_TYPE,
    "pde.RoutingVersion",
    "routing-versions",
)
OBJECT_TYPE = DOCUMENT_TYPE
REVIEW_ACTION = "pde.routing_version.review"
REVIEW_PERMISSION = REVIEW_ACTION
REQUIRED_RESPONSIBILITY_CODE = "RESP_TECH_PROCESS_001"
APPROVED_PROJECTION = "workflow_approved"
ALLOWED_TRANSITIONS = (("draft", "reviewed"),)


class RoutingVersionReviewError(ValueError):
    def __init__(self, code, message, http_status=422, details=None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _company_id(version):
    if version.routing_id:
        return version.routing.company_id
    if version.product_id:
        return version.product.company_id
    return None


def _snapshot(version):
    return {
        "routingVersionId": version.pk,
        "routingVersionNo": version.routing_version,
        "revision": version.revision,
        "status": version.status,
        "approvalState": version.approval_state,
        "routingId": version.routing_id,
        "routingCode": version.routing.routing_code if version.routing_id else "",
        "companyId": _company_id(version),
        "updatedAt": version.updated_at.isoformat() if version.updated_at else "",
    }


def resolve_workflow_template():
    """Resolve one configured RoutingVersion review definition without mutation."""

    definitions = list(
        ProcessDefinition.objects.filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            active=True,
        ).prefetch_related("nodes").order_by("pk")
    )
    if not definitions:
        return None, None, {
            "code": "ROUTING_VERSION_WORKFLOW_TEMPLATE_MISSING",
            "message": "正式库缺少可合法适用于工艺路线版本评审的Workflow模板。",
        }
    if len(definitions) != 1:
        return None, None, {
            "code": "ROUTING_VERSION_WORKFLOW_TEMPLATE_AMBIGUOUS",
            "message": "正式库存在多个可适用工艺路线版本Workflow模板，无法唯一解析。",
            "definitionIds": [row.pk for row in definitions],
        }
    definition = definitions[0]
    nodes = list(definition.nodes.filter(active=True).order_by("sequence", "pk"))
    if len(nodes) != 1:
        return definition, None, {
            "code": "ROUTING_VERSION_WORKFLOW_NODE_INVALID",
            "message": "工艺路线版本最小评审模板必须且只能包含一个启用评审节点。",
            "nodeIds": [row.pk for row in nodes],
        }
    node = nodes[0]
    if node.business_action_code != REVIEW_PERMISSION:
        return definition, node, {
            "code": "ROUTING_VERSION_WORKFLOW_NODE_ACTION_INVALID",
            "message": "工艺路线版本评审节点必须引用独立的正式评审权限。",
            "permissionCode": node.business_action_code,
            "expectedPermissionCode": REVIEW_PERMISSION,
        }
    permission = Permission.objects.filter(code=REVIEW_PERMISSION).first()
    if not permission:
        return definition, node, {
            "code": "ROUTING_VERSION_REVIEW_PERMISSION_MISSING",
            "message": "Workflow评审节点引用的工艺路线版本正式评审权限不存在。",
            "permissionCode": REVIEW_PERMISSION,
        }
    return definition, node, None


def eligible_review_actors(company_id, routing_version_id):
    """Resolve formal non-superuser reviewers through existing authority facts."""

    role_ids = set(
        RolePermission.objects.filter(permission__code=REVIEW_PERMISSION)
        .values_list("role_id", flat=True)
    )
    if not role_ids:
        return []
    assignments = UserRoleScopeAssignment.objects.filter(
        organization_id=company_id,
        role_id__in=role_ids,
        active=True,
        user__is_active=True,
        user__is_superuser=False,
    )
    user_ids = set(assignments.values_list("user_id", flat=True))
    matched_roles_by_user = {}
    for user_id, role_code in assignments.values_list("user_id", "role__code"):
        matched_roles_by_user.setdefault(user_id, set()).add(role_code)
    employees = {
        row.user_id: row
        for row in formal_employee_queryset(
            Employee.objects.select_related("position_ref"), company_id=company_id,
        ).filter(user_id__in=user_ids)
    }
    rows = []
    for user in User.objects.filter(pk__in=user_ids).order_by("pk"):
        decision = AuthorizationService.decide(
            user=user,
            action_code=REVIEW_PERMISSION,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "entity": "routing-versions",
                "id": routing_version_id,
            },
            context={"moduleCode": "PDE", "businessWrite": True},
        )
        employee = employees.get(user.pk)
        position = employee.position_ref if employee else None
        responsibilities = list(
            PositionResponsibility.objects.filter(
                position=position,
                active=True,
                responsibility__is_active=True,
                responsibility__status="ACTIVE",
            ).values_list("responsibility__code", flat=True)
        ) if position else []
        if (
            not decision.get("allowed")
            or not employee
            or REQUIRED_RESPONSIBILITY_CODE not in responsibilities
        ):
            continue
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "departmentId": employee.department_ref_id,
            "positionId": position.pk,
            "positionCode": position.code,
            "positionName": position.name,
            "matchedRoleCodes": sorted(matched_roles_by_user.get(user.pk, set())),
            "scopeCodes": decision.get("scope", {}).get("codes", []),
            "responsibilityCodes": responsibilities,
            "requiredResponsibilityCode": REQUIRED_RESPONSIBILITY_CODE,
            "authorizationDecisionCode": decision.get("decisionCode", ""),
        })
    return rows


def workflow_projection(version):
    instances = list(
        WorkflowInstance.objects.filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            document_id=version.pk,
        ).select_related("process_definition").order_by("pk")
    )
    workflow = instances[0] if len(instances) == 1 else None
    decisions = list(
        ApprovalDecision.objects.filter(
            task__workflow_instance=workflow,
            decision="approved",
            action_id=REVIEW_ACTION,
        ).select_related("actor", "task").order_by("created_at", "pk")
    ) if workflow else []
    if not workflow:
        projected = "not_submitted"
    elif workflow.status == WorkflowInstance.Status.APPROVED and decisions:
        projected = APPROVED_PROJECTION
    elif workflow.status == WorkflowInstance.Status.REJECTED:
        projected = "workflow_rejected"
    else:
        projected = "workflow_pending"
    return {
        "instances": instances,
        "workflow": workflow,
        "decisions": decisions,
        "projectionState": projected,
        "projectionConsistent": len(instances) <= 1 and version.approval_state == projected,
    }


def _gate(code, label, passed, evidence, details=None):
    return {
        "code": code,
        "label": label,
        "statusCode": "PASS" if passed else "BLOCKED",
        "statusLabel": "通过" if passed else "阻断",
        "evidence": evidence,
        "details": details or {},
    }


def project_draft_completeness(version):
    """Project review-only gates; capacity and planning data are out of scope."""

    company_id = _company_id(version)
    identity_ready = bool(version.routing_id and company_id)
    gates = [
        _gate(
            "ROUTING_VERSION_IDENTITY",
            "路线版本正式身份",
            identity_ready,
            (
                f"Routing {version.routing_id} / RoutingVersion {version.pk} / "
                f"{version.routing_version} / Rev{version.revision}"
                if identity_ready else "路线版本未完整绑定正式Routing和组织。"
            ),
        )
    ]

    source_rows = list(
        MasterDataWriteRequest.objects.filter(
            organization_id=company_id,
            action_code="pde.routing_version.create_successor",
            entity_type="routing-versions",
            target_entity_id=str(version.pk),
            status=MasterDataWriteRequest.Status.COMMITTED,
        ).order_by("pk")
    ) if company_id and version.revision > 1 else []
    source_id = None
    if len(source_rows) == 1 and isinstance(source_rows[0].result, dict):
        source_id = source_rows[0].result.get("sourceRoutingVersionId")
    source = RoutingVersion.objects.filter(pk=source_id).first() if source_id else None
    source_ready = (
        version.revision == 1
        or (
            len(source_rows) == 1
            and source is not None
            and source.routing_id == version.routing_id
            and source.revision < version.revision
            and source.status in {"reviewed", "released", "obsolete"}
        )
    )
    gates.append(_gate(
        "SOURCE_VERSION_LINEAGE",
        "来源版本承接",
        source_ready,
        (
            "首版无需后续版本来源。" if version.revision == 1 else
            f"来源 RoutingVersion {source.pk} / Rev{source.revision} / {source.status}；承接请求 {source_rows[0].pk}。"
            if source_ready else "未找到唯一、同路线且处于终态的后续版本来源事实。"
        ),
        {"sourceRoutingVersionId": source.pk if source else None},
    ))

    steps = list(version.steps.select_related("operation").order_by("sequence", "pk"))
    sequences = [step.sequence for step in steps]
    sequence_ready = bool(steps) and sequences == list(range(1, len(steps) + 1))
    gates.append(_gate(
        "ROUTING_STEPS_COMPLETE",
        "工序及顺序完整",
        sequence_ready,
        f"读取到 {len(steps)} 道正式工序；顺序为1..{len(steps)}。" if sequence_ready
        else "工序为空、顺序重复或顺序不连续。",
        {"stepCount": len(steps), "sequences": sequences},
    ))

    sequence_set = set(sequences)
    dependency_errors = []
    for step in steps:
        predecessors = step.predecessor_sequences
        if not isinstance(predecessors, list):
            dependency_errors.append({"sequence": step.sequence, "reason": "前置依赖不是列表"})
            continue
        if len(predecessors) != len(set(predecessors)):
            dependency_errors.append({"sequence": step.sequence, "reason": "前置依赖重复"})
        for predecessor in predecessors:
            if (
                not isinstance(predecessor, int)
                or predecessor not in sequence_set
                or predecessor >= step.sequence
            ):
                dependency_errors.append({
                    "sequence": step.sequence,
                    "predecessor": predecessor,
                    "reason": "前置依赖必须引用当前版本中更早的步骤",
                })
    gates.append(_gate(
        "ROUTING_DEPENDENCIES_VALID",
        "工序前置依赖",
        not dependency_errors,
        "全部前置依赖均引用当前版本中更早的有效步骤。" if not dependency_errors
        else "存在无效、重复或逆向前置依赖。",
        {"errors": dependency_errors},
    ))

    contexts = exact_contexts_for_version(version)
    context_ready = len(contexts) == 1
    context_snapshot = contexts[0]["snapshot"] if context_ready else {}
    gates.append(_gate(
        "FORMAL_ORDER_ENGINEERING_CONTEXT",
        "正式订单工程与已发布BOM关系",
        context_ready,
        (
            f"{context_snapshot.get('salesOrderNo')} / 行{context_snapshot.get('salesOrderLineNo')} / "
            f"{context_snapshot.get('orderEngineeringInstanceNo')} / BOM {context_snapshot.get('bomVersionNo')}"
            if context_ready else "当前路线版本无法唯一绑定正式订单工程与已发布BOM版本。"
        ),
        {"contextCount": len(contexts), "context": context_snapshot},
    ))

    applicability_rows = []
    if context_ready:
        context = contexts[0]
        for step in steps:
            resolved = RoutingStepApplicabilityResolver.resolve(
                step,
                engineering_calculation=context["engineeringCalculation"],
                order_engineering_instance=context["orderEngineeringInstance"],
                order_engineering_baseline=context["orderEngineeringBaseline"],
                bom_version=context["bomVersion"],
            )
            applicability_rows.append({
                "stepId": step.pk,
                "sequence": step.sequence,
                "operationCode": step.operation.code,
                "operationName": step.operation.name,
                "mode": resolved.get("mode"),
                "modeLabel": resolved.get("modeLabel"),
                "result": resolved.get("result"),
                "resultLabel": resolved.get("resultLabel"),
                "formalApplicabilityValidated": resolved.get("formalApplicabilityValidated"),
                "pendingCode": resolved.get("pendingCode"),
                "pendingReason": resolved.get("pendingReason"),
                "manualDecision": resolved.get("manualDecision"),
                "manualDecisionConfirmedBy": resolved.get("manualDecisionConfirmedBy"),
                "manualDecisionAuditId": resolved.get("manualDecisionAuditId"),
            })
    applicability_ready = bool(applicability_rows) and all(
        row["formalApplicabilityValidated"] and row["result"] in {"REQUIRED", "NOT_APPLICABLE"}
        for row in applicability_rows
    )
    gates.append(_gate(
        "STEP_APPLICABILITY_RESOLVED",
        "工序适用性正式结论",
        applicability_ready,
        "全部步骤均具有正式适用性合同，条件步骤已形成精确订单工程结论。"
        if applicability_ready else "存在缺失、待确认、冲突或身份无效的工序适用性。",
        {
            "requiredCount": sum(row["result"] == "REQUIRED" for row in applicability_rows),
            "notApplicableCount": sum(row["result"] == "NOT_APPLICABLE" for row in applicability_rows),
            "pendingCount": sum(row["result"] not in {"REQUIRED", "NOT_APPLICABLE"} for row in applicability_rows),
            "rows": applicability_rows,
        },
    ))

    return {
        "complete": all(row["statusCode"] == "PASS" for row in gates),
        "gates": gates,
        "stepCount": len(steps),
        "contextCount": len(contexts),
        "sourceRoutingVersionId": source.pk if source else None,
        "applicabilityRows": applicability_rows,
    }


def review_readback(version):
    projection = workflow_projection(version)
    workflow = projection["workflow"]
    decisions = projection["decisions"]
    decision = decisions[0] if len(decisions) == 1 else None
    transition = BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        action_code=REVIEW_ACTION,
        target_state="reviewed",
    ).select_related("operator", "workflow_instance").order_by("-version", "-pk").first()
    request = MasterDataWriteRequest.objects.filter(
        organization_id=_company_id(version),
        action_code=REVIEW_ACTION,
        entity_type=OBJECT_TYPE,
        target_entity_id=str(version.pk),
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).order_by("-pk").first()
    completed = bool(
        version.status in {"reviewed", "released", "obsolete"}
        and version.approval_state == APPROVED_PROJECTION
        and workflow
        and workflow.status == WorkflowInstance.Status.APPROVED
        and decision
        and transition
    )
    return {
        "completed": completed,
        "projectionConsistent": projection["projectionConsistent"],
        "workflowInstanceId": workflow.pk if workflow else None,
        "workflowInstanceNo": workflow.instance_no if workflow else "",
        "workflowStatusCode": workflow.status if workflow else "",
        "decisionId": decision.pk if decision else None,
        "decisionCode": decision.decision if decision else "",
        "decisionComment": decision.comment if decision else "",
        "actorId": decision.actor_id if decision else None,
        "actorUsername": decision.actor.username if decision else "",
        "actorRealName": decision.actor.real_name if decision else "",
        "reviewedAt": decision.completed_at.isoformat() if decision else "",
        "businessStateTransitionId": transition.pk if transition else None,
        "auditReference": transition.audit_reference if transition else "",
        "requestIdentity": request.idempotency_key if request else "",
        "writeRequestId": request.pk if request else None,
        "actionCode": REVIEW_ACTION,
    }


def project_review_preflight(version, user):
    completeness = project_draft_completeness(version)
    permission_exists = Permission.objects.filter(code=REVIEW_PERMISSION).exists()
    definition, node, template_error = resolve_workflow_template()
    actors = eligible_review_actors(_company_id(version), version.pk) if permission_exists else []
    current_actor = next((row for row in actors if row["userId"] == user.pk), None)
    readback = review_readback(version)
    gates = list(completeness["gates"])
    if version.usage_purpose == 'TEST_BUSINESS':
        gates.insert(0, _gate('TEST_ROUTE_FORMAL_USE_DENIED', '测试路线用途限制', False, '测试路线草稿禁止正式评审、发布和制造承接。'))
    gates.extend([
        _gate(
            "REVIEW_PERMISSION_REGISTERED",
            "正式评审权限定义",
            permission_exists,
            f"已存在 {REVIEW_PERMISSION}。" if permission_exists
            else f"正式库尚未登记 {REVIEW_PERMISSION}。",
        ),
        _gate(
            "WORKFLOW_TEMPLATE_READY",
            "正式评审Workflow模板",
            not template_error,
            (
                f"Definition {definition.pk} / Node {node.pk} / {node.business_action_code}"
                if not template_error else template_error["message"]
            ),
            template_error or {},
        ),
        _gate(
            "CURRENT_ACTOR_AUTHORIZED",
            "当前评审人身份与权限",
            bool(current_actor),
            (
                f"{current_actor['realName']} / {current_actor['username']} / "
                f"{current_actor['positionCode']} / ORGANIZATION:{_company_id(version)}"
                if current_actor else
                f"当前账号未同时满足 {REVIEW_PERMISSION}、ORGANIZATION:{_company_id(version)}、"
                f"正式员工岗位及职责 {REQUIRED_RESPONSIBILITY_CODE}。"
            ),
        ),
    ])
    first_blocker = next((row for row in gates if row["statusCode"] != "PASS"), None)
    review_allowed = bool(
        version.status == "draft"
        and not first_blocker
        and not readback["completed"]
    )
    return {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": REVIEW_ACTION,
        "permissionCode": REVIEW_PERMISSION,
        "requiredResponsibilityCode": REQUIRED_RESPONSIBILITY_CODE,
        "targetStatusCode": "reviewed",
        "targetStatusLabel": "已评审",
        "reviewAllowed": review_allowed,
        "decisionCode": (
            "PASS_READY_FOR_FORMAL_REVIEW" if review_allowed else
            "PASS_FORMAL_REVIEW_COMPLETE" if readback["completed"] else
            "BLOCKED"
        ),
        "decisionLabel": (
            "允许正式评审" if review_allowed else
            "正式评审已完成" if readback["completed"] else
            "暂不可正式评审"
        ),
        "firstBlockerCode": first_blocker["code"] if first_blocker else "",
        "firstBlockerLabel": first_blocker["label"] if first_blocker else "",
        "firstBlockerMessage": first_blocker["evidence"] if first_blocker else "",
        "gates": gates,
        "gatePassCount": sum(row["statusCode"] == "PASS" for row in gates),
        "gateFailCount": sum(row["statusCode"] != "PASS" for row in gates),
        "workflowRuntime": {
            "definitionId": definition.pk if definition else None,
            "definitionCode": definition.definition_code if definition else "",
            "nodeId": node.pk if node else None,
            "nodeCode": node.node_code if node else "",
            "configurationSourceCode": (
                "SYSTEM_CATALOG"
                if definition and definition.definition_code == CANONICAL_DEFINITION["definition_code"]
                else "EXISTING_FORMAL_CONFIGURATION" if definition else ""
            ),
            "configurationSourceLabel": (
                "系统目录自动生成"
                if definition and definition.definition_code == CANONICAL_DEFINITION["definition_code"]
                else "既有正式配置" if definition else "尚未生成"
            ),
            "blocker": template_error or {},
        },
        "eligibleReviewActors": actors,
        "currentActor": current_actor or {},
        "completeness": completeness,
        "reviewReadback": readback,
    }


def _require_actor(version, user):
    actor = next(
        (
            row for row in eligible_review_actors(_company_id(version), version.pk)
            if row["userId"] == user.pk
        ),
        None,
    )
    if not actor:
        raise RoutingVersionReviewError(
            "PERMISSION_DENIED",
            "当前登录人员不具备工艺路线版本正式评审的角色、范围、员工、岗位与职责资格。",
            403,
            {
                "permissionCode": REVIEW_PERMISSION,
                "requiredResponsibilityCode": REQUIRED_RESPONSIBILITY_CODE,
            },
        )
    return actor


def _reserve_request(*, version, user, reason, key):
    key = str(key or "").strip()
    if not key:
        raise RoutingVersionReviewError(
            "IDEMPOTENCY_KEY_REQUIRED", "正式评审必须提供Idempotency-Key。", 409,
        )
    payload = {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": REVIEW_ACTION,
        "routingVersionId": version.pk,
        "targetState": "reviewed",
        "actorId": user.pk,
        "reason": reason,
    }
    request_hash = _hash(payload)
    existing = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=_company_id(version),
        action_code=REVIEW_ACTION,
        idempotency_key=key,
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise RoutingVersionReviewError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同工艺路线版本评审payload。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise RoutingVersionReviewError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity已有未完成的工艺路线版本评审。",
            409,
        )
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=_company_id(version),
        source_system="PCE_ROUTING_VERSION_REVIEW",
        source_type="BUSINESS_ACTION_SCOPE",
        source_object_type=OBJECT_TYPE,
        external_id=f"RoutingVersion:{version.pk}",
        defaults={
            "target_entity_type": OBJECT_TYPE,
            "target_entity_id": str(version.pk),
            "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": _hash({"objectType": OBJECT_TYPE, "objectId": version.pk}),
            "audit_metadata": {"contractVersion": CONTROL_CONTRACT},
        },
    )
    if identity.target_entity_type != OBJECT_TYPE or identity.target_entity_id != str(version.pk):
        raise RoutingVersionReviewError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "现有ExternalIdentity与当前工艺路线版本范围不一致。",
            409,
        )
    request = MasterDataWriteRequest.objects.create(
        organization_id=_company_id(version),
        action_code=REVIEW_ACTION,
        entity_type=OBJECT_TYPE,
        idempotency_key=key,
        request_hash=request_hash,
        source_identity=identity,
        audit_metadata=payload,
    )
    return request, False


def _commit_request(request, result, version):
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(version.pk)
    request.result = result
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])


@transaction.atomic
def review_routing_version(*, object_id, user, reason, idempotency_key, action=""):
    reason = str(reason or "").strip()
    if not reason:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_REVIEW_REASON_REQUIRED", "正式评审意见必须填写。", 422,
        )
    if action and str(action).strip() != REVIEW_ACTION:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_REVIEW_ACTION_CONFLICT",
            "请求action与工艺路线版本正式评审动作不一致。",
            409,
        )
    version = RoutingVersion.objects.select_for_update().select_related(
        "routing", "routing__company", "product", "product__company",
    ).filter(pk=object_id).first()
    if not version:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_NOT_FOUND", "待评审工艺路线版本不存在。", 404,
        )
    if version.usage_purpose == 'TEST_BUSINESS':
        raise RoutingVersionReviewError('TEST_ROUTE_FORMAL_USE_DENIED', '测试路线草稿禁止正式评审、发布和制造承接。', 409)
    if _company_id(version) != user.company_id:
        raise RoutingVersionReviewError(
            "SCOPE_DENIED", "工艺路线版本不属于当前登录用户的正式组织范围。", 403,
        )
    request, replayed = _reserve_request(
        version=version,
        user=user,
        reason=reason,
        key=idempotency_key,
    )
    if replayed:
        return {**request.result, "idempotentReplay": True}
    if version.status != "draft":
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_STATE_CONFLICT",
            f"正式评审要求当前状态为draft，实际为{version.status}。",
            409,
        )
    definition, node, template_error = resolve_workflow_template()
    if template_error:
        raise RoutingVersionReviewError(
            template_error["code"], template_error["message"], 422, template_error,
        )
    authorization = _require_actor(version, user)
    completeness = project_draft_completeness(version)
    failed = [row for row in completeness["gates"] if row["statusCode"] != "PASS"]
    if failed:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_REVIEW_GATE_BLOCKED",
            "工艺路线版本评审完整性Gate未全部通过。",
            422,
            {"failedGates": failed},
        )
    review_content_snapshot = routing_version_content_snapshot(version, completeness)
    review_content_hash = content_hash(review_content_snapshot)
    workflows = list(
        WorkflowInstance.objects.select_for_update().filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            document_id=version.pk,
        ).order_by("pk")
    )
    if workflows:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_WORKFLOW_ALREADY_EXISTS",
            "该工艺路线版本已有正式Workflow实例，不得重复形成评审决定。",
            409,
        )
    matched_roles = authorization.get("matchedRoleCodes") or []
    if not matched_roles:
        raise RoutingVersionReviewError(
            "ROUTING_VERSION_REVIEW_ROLE_REQUIRED",
            "当前评审人员没有与Workflow节点权限匹配的正式角色。",
            403,
        )
    workflow = WorkflowInstance.objects.create(
        instance_no=f"WFI-ROUTING-{version.pk}-{request.pk}",
        process_definition=definition,
        document_type=DOCUMENT_TYPE,
        document_id=version.pk,
        status=WorkflowInstance.Status.PENDING,
        current_step=1,
        total_steps=1,
    )
    task = ApprovalTask.objects.create(
        task_no=f"APT-ROUTING-{version.pk}-{request.pk}-01",
        workflow_instance=workflow,
        step_no=1,
        required_role_code=matched_roles[0],
        minimum_approvals=1,
        allow_parallel=False,
        status=ApprovalTask.Status.PENDING,
    )
    decision = ApprovalDecision.objects.create(
        task=task,
        decision_sequence=1,
        actor=user,
        decision="approved",
        comment=reason,
        action_id=REVIEW_ACTION,
        idempotency_key=str(idempotency_key).strip(),
        decision_hash=_hash({
            "workflowInstanceId": workflow.pk,
            "taskId": task.pk,
            "actorId": user.pk,
            "decision": "approved",
            "requestIdentity": str(idempotency_key).strip(),
        }),
    )
    task.status = ApprovalTask.Status.APPROVED
    task.version += 1
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "version", "completed_at"])
    workflow.status = WorkflowInstance.Status.APPROVED
    workflow.version += 1
    workflow.completed_at = timezone.now()
    workflow.save(update_fields=["status", "version", "completed_at"])
    before = _snapshot(version)
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=REVIEW_ACTION,
        actor=user,
        organization_id=_company_id(version),
        target_type=OBJECT_TYPE,
        target_id=version.pk,
        target_label=f"{version.routing_version} / Rev{version.revision}",
        reason=reason,
        before_snapshot=before,
        after_snapshot={
            **before,
            "status": "reviewed",
            "approvalState": APPROVED_PROJECTION,
            "workflowInstanceId": workflow.pk,
            "workflowDecisionId": decision.pk,
            "requestIdentity": str(idempotency_key).strip(),
            "authorization": authorization,
            "reviewCompleteness": completeness,
            "reviewContentSnapshot": review_content_snapshot,
            "reviewContentHash": review_content_hash,
            "controlContract": CONTROL_CONTRACT,
        },
    )
    transition = transition_business_object(
        business_object=version,
        object_type=OBJECT_TYPE,
        source_state="draft",
        target_state="reviewed",
        action_code=REVIEW_ACTION,
        operator=user,
        reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        workflow_instance=workflow,
        allowed_transitions=ALLOWED_TRANSITIONS,
        version_field=None,
    )
    version.approval_state = APPROVED_PROJECTION
    version.save(update_fields=["approval_state", "updated_at"])
    result = {
        "contractVersion": CONTROL_CONTRACT,
        "idempotentReplay": False,
        "routingVersion": _snapshot(version),
        "workflow": {
            "instanceId": workflow.pk,
            "instanceNo": workflow.instance_no,
            "statusCode": workflow.status,
            "taskId": task.pk,
            "decisionId": decision.pk,
            "decisionActorId": decision.actor_id,
            "decisionAt": decision.completed_at.isoformat(),
        },
        "businessStateTransition": {
            "id": transition.pk,
            "objectType": transition.object_type,
            "objectId": transition.object_id,
            "fromState": transition.source_state,
            "toState": transition.target_state,
            "actorId": transition.operator_id,
            "occurredAt": transition.timestamp.isoformat(),
            "workflowInstanceId": transition.workflow_instance_id,
            "auditReference": transition.audit_reference,
        },
        "auditId": audit.pk,
        "requestIdentity": request.idempotency_key,
        "writeRequestId": request.pk,
    }
    _commit_request(request, result, version)
    return result


__all__ = [
    "APPROVED_PROJECTION",
    "CONTROL_CONTRACT",
    "REVIEW_ACTION",
    "REVIEW_PERMISSION",
    "REQUIRED_RESPONSIBILITY_CODE",
    "RoutingVersionReviewError",
    "eligible_review_actors",
    "project_draft_completeness",
    "project_review_preflight",
    "review_readback",
    "review_routing_version",
]
