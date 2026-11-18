"""Controlled BOMVersion review/release lifecycle on the shared PCE ledgers.

The service deliberately creates no workflow configuration.  A formal active
ProcessDefinition and node must already exist before a business action can run.
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
    SegregationOfDutiesAuthority,
    WorkflowInstance,
)
from workflow_runtime.state_transitions import transition_business_object

from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
from .models import BOMVersion
from .product_bom_detail_projection import project_product_bom_material_detail


CONTROL_CONTRACT = "PCE-BOM-VERSION-CONTROL-CHAIN-V1.0"
DOCUMENT_TYPE = "BOMVersion"
WORKFLOW_DOCUMENT_TYPES = (
    DOCUMENT_TYPE,
    "pde.BOMVersion",
    "bom-versions",
    "EngineeringVersion",
)
OBJECT_TYPE = DOCUMENT_TYPE
REVIEW_ACTION = "pde.bom_version.review"
RELEASE_ACTION = "pde.bom_version.release"
OBSOLETE_ACTION = "pde.bom_version.obsolete"
REVIEW_PERMISSION = REVIEW_ACTION
RELEASE_PERMISSION = RELEASE_ACTION
OBSOLETE_PERMISSION = "production.engineering.version.release"
REQUIRED_RESPONSIBILITY_BY_PERMISSION = {
    REVIEW_PERMISSION: "BOM_VERSION_FORMAL_REVIEW",
    RELEASE_PERMISSION: "BOM_VERSION_FORMAL_RELEASE",
}
APPROVED_PROJECTION = "workflow_approved"
ALLOWED_TRANSITIONS = (
    ("draft", "reviewed"),
    ("reviewed", "released"),
    ("released", "obsolete"),
)
UPSTREAM_GATE_CODES = (
    "IDENTITY_UNIQUE",
    "BOM_REVISION_UNIQUE",
    "FORMAL_SCOPE_CONSISTENT",
    "BASELINE_CURRENT",
    "CALCULATION_CURRENT",
    "BOM_ITEMS_COMPLETE",
    "SOURCE_REQUIREMENTS_COMPLETE",
    "NO_COMPETING_VERSION",
    "NO_RELEASED_VERSION_CONFLICT",
)


class BomVersionControlError(ValueError):
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


def _snapshot(version):
    return {
        "bomVersionId": version.pk,
        "bomVersionNo": version.bom_version,
        "revision": version.revision,
        "status": version.status,
        "approvalState": version.approval_state,
        "productBomId": version.bom_id,
        "companyId": version.bom.company_id,
        "updatedAt": version.updated_at.isoformat() if version.updated_at else "",
    }


def resolve_workflow_template():
    """Resolve one existing, semantically applicable definition without creating it."""

    definitions = list(
        ProcessDefinition.objects.filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            active=True,
        ).prefetch_related("nodes").order_by("pk")
    )
    if not definitions:
        return None, None, {
            "code": "BOM_VERSION_WORKFLOW_TEMPLATE_MISSING",
            "message": "正式库缺少可合法适用于BOMVersion评审的Workflow模板。",
        }
    if len(definitions) != 1:
        return None, None, {
            "code": "BOM_VERSION_WORKFLOW_TEMPLATE_AMBIGUOUS",
            "message": "正式库存在多个可适用Workflow模板，无法唯一解析。",
            "definitionIds": [row.pk for row in definitions],
        }
    definition = definitions[0]
    nodes = list(definition.nodes.filter(active=True).order_by("sequence", "pk"))
    if len(nodes) != 1:
        return definition, None, {
            "code": "BOM_VERSION_WORKFLOW_NODE_INVALID",
            "message": "BOMVersion最小评审模板必须且只能包含一个启用评审节点。",
            "nodeIds": [row.pk for row in nodes],
        }
    node = nodes[0]
    if node.business_action_code != REVIEW_PERMISSION:
        return definition, node, {
            "code": "BOM_VERSION_WORKFLOW_NODE_ACTION_INVALID",
            "message": "BOMVersion正式评审节点必须引用独立的BOM版本正式评审权限。",
            "permissionCode": node.business_action_code,
            "expectedPermissionCode": REVIEW_PERMISSION,
        }
    permission = Permission.objects.filter(code=node.business_action_code).first()
    if not permission:
        return definition, node, {
            "code": "BOM_VERSION_REVIEW_PERMISSION_MISSING",
            "message": "Workflow评审节点引用的既有正式权限不存在。",
            "permissionCode": node.business_action_code,
        }
    return definition, node, None


def eligible_action_actors(company_id, bom_version_id, permission_code):
    """Resolve non-superuser actors through existing role/scope/employee facts."""

    required_responsibility_code = REQUIRED_RESPONSIBILITY_BY_PERMISSION.get(permission_code)
    role_ids = set(
        RolePermission.objects.filter(permission__code=permission_code)
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
    for user in User.objects.filter(pk__in=user_ids).defer("password").order_by("pk"):
        decision = AuthorizationService.decide(
            user=user,
            action_code=permission_code,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "entity": "bom-versions",
                "id": bom_version_id,
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
        responsibility_ready = bool(responsibilities) and (
            required_responsibility_code is None
            or required_responsibility_code in responsibilities
        )
        if not decision.get("allowed") or not employee or not responsibility_ready:
            continue
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "departmentId": employee.department_ref_id,
            "positionId": position.pk,
            "positionCode": position.code,
            "roleCodes": decision.get("roleCodes", []),
            "matchedRoleCodes": sorted(matched_roles_by_user.get(user.pk, set())),
            "scopeCodes": decision.get("scope", {}).get("codes", []),
            "responsibilityCodes": responsibilities,
            "requiredResponsibilityCode": required_responsibility_code or "",
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
        ).select_related("actor", "task").defer("actor__password").order_by("created_at", "pk")
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


def control_chain_readiness(version):
    definition, node, template_error = resolve_workflow_template()
    company_id = version.bom.company_id
    review_permission = REVIEW_PERMISSION
    review_actors = (
        eligible_action_actors(company_id, version.pk, review_permission)
        if node and not template_error else []
    )
    release_actors = eligible_action_actors(
        company_id, version.pk, RELEASE_PERMISSION,
    )
    separated_pairs = [
        {"reviewUserId": review["userId"], "releaseUserId": release["userId"]}
        for review in review_actors
        for release in release_actors
        if review["userId"] != release["userId"]
    ]
    workflow_ready = not template_error
    sod_ready = workflow_ready and bool(separated_pairs)
    current_business_action = {
        "draft": "等待正式评审授权",
        "reviewed": "正式评审已完成，等待独立发布授权",
        "released": "正式发布已完成",
        "obsolete": "版本已失效",
    }.get(version.status, "当前状态无可用正式动作")
    return {
        "contractVersion": CONTROL_CONTRACT,
        "controlChainIntegrated": True,
        "controlChainStatusCode": "INTEGRATED",
        "controlChainStatusLabel": "已接入",
        "workflowRuntime": {
            "statusCode": "READY" if workflow_ready else "BLOCKED",
            "definitionId": definition.pk if definition else None,
            "definitionCode": definition.definition_code if definition else "",
            "nodeId": node.pk if node else None,
            "nodeCode": node.node_code if node else "",
            "reviewPermissionCode": review_permission,
            "blocker": template_error or {},
        },
        "businessStateTransition": {
            "statusCode": "READY",
            "objectType": OBJECT_TYPE,
            "service": "workflow_runtime.state_transitions.transition_business_object",
        },
        "requestIdempotency": {
            "statusCode": "READY",
            "ledger": "masterdata.MasterDataWriteRequest",
            "identity": "masterdata.ExternalIdentity",
        },
        "segregationOfDuties": {
            "statusCode": "READY" if sod_ready else "BLOCKED",
            "rule": "review actor != release actor",
            "reviewActors": review_actors,
            "releaseActors": release_actors,
            "separatedActorPairCount": len(separated_pairs),
            "blockerCode": "" if sod_ready else (
                template_error["code"] if template_error else "DISTINCT_ACTOR_ASSIGNMENT_REQUIRED"
            ),
        },
        "formalExecutionReady": workflow_ready and sod_ready,
        "currentBusinessAction": current_business_action,
    }


def _require_actor(version, user, permission_code):
    candidates = eligible_action_actors(
        version.bom.company_id, version.pk, permission_code,
    )
    actor = next((row for row in candidates if row["userId"] == user.pk), None)
    if not actor:
        raise BomVersionControlError(
            "PERMISSION_DENIED",
            "当前登录人员不具备该BOMVersion动作的正式角色、范围、员工、岗位与职责资格。",
            403,
            {"permissionCode": permission_code},
        )
    return actor


def _reserve_request(*, version, user, action_code, target_state, reason, key):
    key = str(key or "").strip()
    if not key:
        raise BomVersionControlError(
            "IDEMPOTENCY_KEY_REQUIRED", "正式状态动作必须提供Idempotency-Key。", 409,
        )
    request_payload = {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": action_code,
        "bomVersionId": version.pk,
        "targetState": target_state,
        "actorId": user.pk,
        "reason": str(reason or "").strip(),
    }
    request_hash = _hash(request_payload)
    existing = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=version.bom.company_id,
        action_code=action_code,
        idempotency_key=key,
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise BomVersionControlError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同BOMVersion动作或payload。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise BomVersionControlError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity已有未完成的受控动作。",
            409,
        )
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=version.bom.company_id,
        source_system="PCE_BOM_VERSION_CONTROL",
        source_type="BUSINESS_ACTION_SCOPE",
        source_object_type=OBJECT_TYPE,
        external_id=f"BOMVersion:{version.pk}",
        defaults={
            "target_entity_type": OBJECT_TYPE,
            "target_entity_id": str(version.pk),
            "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": _hash({"objectType": OBJECT_TYPE, "objectId": version.pk}),
            "audit_metadata": {"contractVersion": CONTROL_CONTRACT},
        },
    )
    if identity.target_entity_type != OBJECT_TYPE or identity.target_entity_id != str(version.pk):
        raise BomVersionControlError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "现有ExternalIdentity与当前BOMVersion范围不一致。",
            409,
        )
    request = MasterDataWriteRequest.objects.create(
        organization_id=version.bom.company_id,
        action_code=action_code,
        entity_type=OBJECT_TYPE,
        idempotency_key=key,
        request_hash=request_hash,
        source_identity=identity,
        audit_metadata=request_payload,
    )
    return request, False


def _commit_request(request, result, version):
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(version.pk)
    request.result = result
    request.save(update_fields=[
        "status", "target_entity_id", "result", "updated_at",
    ])


def _assert_upstream_gates(version):
    order_item = (
        version.order_engineering_instance.sales_order_item
        if version.order_engineering_instance_id else None
    )
    details = project_product_bom_material_detail(
        bom=version.bom,
        bom_version=version,
        order_item=order_item,
    )
    # Local import avoids coupling the read projection to service import order.
    from .bom_version_release_preflight import project_bom_version_release_preflight

    preflight = project_bom_version_release_preflight(
        version,
        material_details=details,
    )
    gate_map = {row["code"]: row for row in preflight["gates"]}
    failed = [
        gate_map[code]
        for code in UPSTREAM_GATE_CODES
        if code not in gate_map or gate_map[code]["statusCode"] != "PASS"
    ]
    eligibility = FormalManufacturingEligibilityService.resolve(version)
    if not eligibility.get("formalManufacturingEligible"):
        failed.append({
            "code": eligibility.get("decisionCode", "FORMAL_MANUFACTURING_GATE_BLOCKED"),
            "evidence": eligibility.get("message", "正式制造资格未通过。"),
        })
    if failed:
        raise BomVersionControlError(
            "BOM_VERSION_UPSTREAM_GATE_BLOCKED",
            "BOMVersion实时上游Gate未全部通过，停止状态迁移。",
            422,
            {"failedGates": failed},
        )
    return preflight


def _workflow_for_update(version):
    rows = list(
        WorkflowInstance.objects.select_for_update().filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            document_id=version.pk,
        ).order_by("pk")
    )
    if len(rows) > 1:
        raise BomVersionControlError(
            "BOM_VERSION_WORKFLOW_INSTANCE_AMBIGUOUS",
            "同一BOMVersion存在多个正式Workflow实例。",
            409,
        )
    return rows[0] if rows else None


def _approved_review(version):
    projection = workflow_projection(version)
    if (
        not projection["workflow"]
        or projection["workflow"].status != WorkflowInstance.Status.APPROVED
        or len(projection["decisions"]) != 1
    ):
        raise BomVersionControlError(
            "BOM_VERSION_FORMAL_REVIEW_NOT_APPROVED",
            "BOMVersion缺少唯一、已批准的正式评审Workflow决定。",
            422,
        )
    if version.approval_state != APPROVED_PROJECTION:
        raise BomVersionControlError(
            "BOM_VERSION_APPROVAL_PROJECTION_DRIFT",
            "BOMVersion approval_state与Workflow权威事实不一致。",
            409,
        )
    return projection["workflow"], projection["decisions"][0]


def _audit(*, version, user, action_code, reason, before, target_state,
           request_key, workflow, decision, authorization):
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code,
        actor=user,
        organization_id=version.bom.company_id,
        target_type=OBJECT_TYPE,
        target_id=version.pk,
        target_label=version.bom_version,
        reason=reason,
        before_snapshot=before,
        after_snapshot={
            **before,
            "status": target_state,
            "approvalState": (
                APPROVED_PROJECTION if target_state in {"reviewed", "released"}
                else version.approval_state
            ),
            "workflowInstanceId": workflow.pk if workflow else None,
            "workflowDecisionId": decision.pk if decision else None,
            "requestIdentity": request_key,
            "authorization": authorization,
            "controlContract": CONTROL_CONTRACT,
        },
    )


def _result(*, version, transition, audit, request, workflow, decision, replayed=False):
    return {
        "contractVersion": CONTROL_CONTRACT,
        "idempotentReplay": replayed,
        "bomVersion": _snapshot(version),
        "workflow": {
            "instanceId": workflow.pk if workflow else None,
            "instanceNo": workflow.instance_no if workflow else "",
            "statusCode": workflow.status if workflow else "",
            "decisionId": decision.pk if decision else None,
            "decisionActorId": decision.actor_id if decision else None,
            "decisionAt": decision.completed_at.isoformat() if decision else "",
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


def _review(*, version, user, reason, request, request_key):
    if version.status != "draft":
        raise BomVersionControlError(
            "BOM_VERSION_STATE_CONFLICT",
            f"正式评审要求当前状态为draft，实际为{version.status}。",
            409,
        )
    definition, node, template_error = resolve_workflow_template()
    if template_error:
        raise BomVersionControlError(
            template_error["code"], template_error["message"], 422, template_error,
        )
    authorization = _require_actor(version, user, REVIEW_PERMISSION)
    _assert_upstream_gates(version)
    workflow = _workflow_for_update(version)
    if workflow:
        raise BomVersionControlError(
            "BOM_VERSION_WORKFLOW_ALREADY_EXISTS",
            "BOMVersion已有正式Workflow实例；不得以新request identity重复形成决定。",
            409,
        )
    matched_roles = authorization.get("matchedRoleCodes") or []
    if not matched_roles:
        raise BomVersionControlError(
            "BOM_VERSION_REVIEW_ROLE_REQUIRED",
            "当前评审人员没有与Workflow节点权限匹配的正式角色。",
            403,
        )
    workflow = WorkflowInstance.objects.create(
        instance_no=f"WFI-BOM-{version.pk}-{request.pk}",
        process_definition=definition,
        document_type=DOCUMENT_TYPE,
        document_id=version.pk,
        status=WorkflowInstance.Status.PENDING,
        current_step=1,
        total_steps=1,
    )
    task = ApprovalTask.objects.create(
        task_no=f"APT-BOM-{version.pk}-{request.pk}-01",
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
        idempotency_key=request_key,
        decision_hash=_hash({
            "workflowInstanceId": workflow.pk,
            "taskId": task.pk,
            "actorId": user.pk,
            "decision": "approved",
            "requestIdentity": request_key,
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
    audit = _audit(
        version=version,
        user=user,
        action_code=REVIEW_ACTION,
        reason=reason,
        before=before,
        target_state="reviewed",
        request_key=request_key,
        workflow=workflow,
        decision=decision,
        authorization=authorization,
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
    result = _result(
        version=version,
        transition=transition,
        audit=audit,
        request=request,
        workflow=workflow,
        decision=decision,
    )
    _commit_request(request, result, version)
    return result


def _release(*, version, user, reason, request, request_key):
    if version.status != "reviewed":
        raise BomVersionControlError(
            "BOM_VERSION_STATE_CONFLICT",
            f"正式发布要求当前状态为reviewed，实际为{version.status}。",
            409,
        )
    authorization = _require_actor(version, user, RELEASE_PERMISSION)
    workflow, decision = _approved_review(version)
    if decision.actor_id == user.pk:
        raise BomVersionControlError(
            "BOM_VERSION_SEGREGATION_OF_DUTIES_FAILED",
            "正式评审决定人与最终发布执行人必须是不同人员。",
            422,
        )
    sod = SegregationOfDutiesAuthority.objects.filter(
        document_type__in=WORKFLOW_DOCUMENT_TYPES,
    ).first()
    if sod and sod.required_role_separation:
        release_roles = set(authorization.get("matchedRoleCodes") or [])
        if decision.task.required_role_code in release_roles:
            raise BomVersionControlError(
                "BOM_VERSION_ROLE_SEPARATION_FAILED",
                "现有SoD配置要求评审与发布角色分离。",
                422,
            )
    if sod and sod.same_department_restriction:
        review_employee = Employee.objects.filter(user_id=decision.actor_id).first()
        release_employee = Employee.objects.filter(user_id=user.pk).first()
        if (
            review_employee and release_employee
            and review_employee.department_ref_id == release_employee.department_ref_id
        ):
            raise BomVersionControlError(
                "BOM_VERSION_DEPARTMENT_SEPARATION_FAILED",
                "现有SoD配置要求评审与发布部门分离。",
                422,
            )
    _assert_upstream_gates(version)
    before = _snapshot(version)
    audit = _audit(
        version=version,
        user=user,
        action_code=RELEASE_ACTION,
        reason=reason,
        before=before,
        target_state="released",
        request_key=request_key,
        workflow=workflow,
        decision=decision,
        authorization=authorization,
    )
    transition = transition_business_object(
        business_object=version,
        object_type=OBJECT_TYPE,
        source_state="reviewed",
        target_state="released",
        action_code=RELEASE_ACTION,
        operator=user,
        reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        workflow_instance=workflow,
        allowed_transitions=ALLOWED_TRANSITIONS,
        version_field=None,
    )
    result = _result(
        version=version,
        transition=transition,
        audit=audit,
        request=request,
        workflow=workflow,
        decision=decision,
    )
    _commit_request(request, result, version)
    return result


def _obsolete(*, version, user, reason, request, request_key):
    if version.status != "released":
        raise BomVersionControlError(
            "BOM_VERSION_STATE_CONFLICT",
            f"失效动作要求当前状态为released，实际为{version.status}。",
            409,
        )
    authorization = _require_actor(version, user, OBSOLETE_PERMISSION)
    workflow, decision = _approved_review(version)
    before = _snapshot(version)
    audit = _audit(
        version=version,
        user=user,
        action_code=OBSOLETE_ACTION,
        reason=reason,
        before=before,
        target_state="obsolete",
        request_key=request_key,
        workflow=workflow,
        decision=decision,
        authorization=authorization,
    )
    transition = transition_business_object(
        business_object=version,
        object_type=OBJECT_TYPE,
        source_state="released",
        target_state="obsolete",
        action_code=OBSOLETE_ACTION,
        operator=user,
        reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        workflow_instance=workflow,
        allowed_transitions=ALLOWED_TRANSITIONS,
        version_field=None,
    )
    result = _result(
        version=version,
        transition=transition,
        audit=audit,
        request=request,
        workflow=workflow,
        decision=decision,
    )
    _commit_request(request, result, version)
    return result


@transaction.atomic
def transition_bom_version(*, object_id, target_status, user, reason, idempotency_key, action=""):
    target_status = str(target_status or "").strip()
    reason = str(reason or "").strip()
    if target_status not in {"reviewed", "released", "obsolete"}:
        raise BomVersionControlError(
            "BOM_VERSION_TARGET_STATE_INVALID",
            "BOMVersion只允许受控进入reviewed、released或obsolete。",
            409,
        )
    if not reason:
        raise BomVersionControlError(
            "BOM_VERSION_REASON_REQUIRED", "正式状态动作必须提供业务原因。", 422,
        )
    expected_action = {
        "reviewed": REVIEW_ACTION,
        "released": RELEASE_ACTION,
        "obsolete": OBSOLETE_ACTION,
    }[target_status]
    if action and str(action).strip() != expected_action:
        raise BomVersionControlError(
            "BOM_VERSION_ACTION_TARGET_CONFLICT",
            "请求action与targetStatus不一致。",
            409,
        )
    version = BOMVersion.objects.select_for_update().select_related(
        "bom__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "source_calculation",
    ).filter(pk=object_id).first()
    if not version:
        raise BomVersionControlError(
            "BOM_VERSION_NOT_FOUND", "待转换BOMVersion不存在。", 404,
        )
    if version.bom.company_id != user.company_id:
        raise BomVersionControlError(
            "SCOPE_DENIED", "BOMVersion不属于当前登录用户的正式组织范围。", 403,
        )
    from .bom_usage_contract import is_test_source
    if is_test_source(version):
        raise BomVersionControlError('TEST_BUSINESS_PRODUCTION_DENIED','测试业务BOM禁止正式评审和发布。',403)
    request, replayed = _reserve_request(
        version=version,
        user=user,
        action_code=expected_action,
        target_state=target_status,
        reason=reason,
        key=idempotency_key,
    )
    if replayed:
        return {**request.result, "idempotentReplay": True}
    handlers = {
        "reviewed": _review,
        "released": _release,
        "obsolete": _obsolete,
    }
    return handlers[target_status](
        version=version,
        user=user,
        reason=reason,
        request=request,
        request_key=str(idempotency_key).strip(),
    )


def release_readback(version):
    transition = BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        target_state="released",
    ).select_related("operator", "workflow_instance").defer("operator__password").order_by("-version", "-pk").first()
    if not transition:
        return {
            "released": False,
            "actorId": None,
            "actorUsername": "",
            "actorRealName": "",
            "occurredAt": "",
            "workflowInstanceId": None,
            "workflowInstanceNo": "",
            "requestIdentity": "",
            "actionCode": RELEASE_ACTION,
            "decisionCode": "",
        }
    request = MasterDataWriteRequest.objects.filter(
        organization_id=version.bom.company_id,
        action_code=RELEASE_ACTION,
        entity_type=OBJECT_TYPE,
        target_entity_id=str(version.pk),
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).order_by("-pk").first()
    return {
        "released": True,
        "actorId": transition.operator_id,
        "actorUsername": transition.operator.username,
        "actorRealName": transition.operator.real_name,
        "occurredAt": transition.timestamp.isoformat(),
        "workflowInstanceId": transition.workflow_instance_id,
        "workflowInstanceNo": (
            transition.workflow_instance.instance_no
            if transition.workflow_instance_id else ""
        ),
        "requestIdentity": request.idempotency_key if request else "",
        "businessStateTransitionId": transition.pk,
        "auditReference": transition.audit_reference,
        "actionCode": RELEASE_ACTION,
        "decisionCode": "released",
    }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "APPROVED_PROJECTION",
    "BomVersionControlError",
    "CONTROL_CONTRACT",
    "DOCUMENT_TYPE",
    "OBJECT_TYPE",
    "OBSOLETE_ACTION",
    "OBSOLETE_PERMISSION",
    "RELEASE_ACTION",
    "RELEASE_PERMISSION",
    "REVIEW_ACTION",
    "REVIEW_PERMISSION",
    "REQUIRED_RESPONSIBILITY_BY_PERMISSION",
    "WORKFLOW_DOCUMENT_TYPES",
    "control_chain_readiness",
    "eligible_action_actors",
    "release_readback",
    "resolve_workflow_template",
    "transition_bom_version",
    "workflow_projection",
]
