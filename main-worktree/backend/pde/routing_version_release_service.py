"""Dedicated formal release control for an approved RoutingVersion.

The service owns only ``reviewed -> released``.  It does not create an
approval decision or a second workflow, does not grant organization authority,
and cannot be reached through the generic engineering lifecycle transition.
"""

from __future__ import annotations

from hashlib import sha256
import json

from django.db import transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    Responsibility,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition, WorkflowInstance
from workflow_runtime.state_transitions import transition_business_object

from .models import RoutingVersion
from .routing_version_integrity import (
    content_hash,
    review_fact_snapshot,
    routing_version_content_snapshot,
)
from .routing_version_review_service import (
    APPROVED_PROJECTION,
    OBJECT_TYPE,
    REVIEW_ACTION,
    project_draft_completeness,
    review_readback,
)


CONTROL_CONTRACT = "PCE-ROUTING-VERSION-FORMAL-RELEASE-V1.0"
RELEASE_ACTION = "pde.routing_version.release"
RELEASE_PERMISSION = RELEASE_ACTION
REQUIRED_RESPONSIBILITY_CODE = "ROUTING_VERSION_FORMAL_RELEASE"
ALLOWED_TRANSITIONS = (("reviewed", "released"),)


class RoutingVersionReleaseError(ValueError):
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


def _gate(code, label, passed, evidence, details=None):
    return {
        "code": code,
        "label": label,
        "statusCode": "PASS" if passed else "BLOCKED",
        "statusLabel": "通过" if passed else "阻断",
        "evidence": evidence,
        "details": details or {},
    }


def eligible_release_actors(company_id, routing_version_id):
    """Resolve release actors through the complete dedicated authority chain."""

    role_ids = set(
        RolePermission.objects.filter(permission__code=RELEASE_PERMISSION)
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
            Employee.objects.select_related("department_ref", "position_ref"),
            company_id=company_id,
        ).filter(user_id__in=user_ids)
    }
    rows = []
    for user in User.objects.filter(pk__in=user_ids).order_by("pk"):
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
        if not employee or REQUIRED_RESPONSIBILITY_CODE not in responsibilities:
            continue
        decision = AuthorizationService.decide(
            user=user,
            action_code=RELEASE_PERMISSION,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "entity": "routing-versions",
                "id": routing_version_id,
            },
            context={"moduleCode": "PDE", "businessWrite": True},
        )
        if not decision.get("allowed"):
            continue
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "departmentId": employee.department_ref_id,
            "departmentCode": employee.department_ref.code if employee.department_ref_id else "",
            "departmentName": employee.department_ref.name if employee.department_ref_id else "",
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


def _review_audit(version):
    readback = review_readback(version)
    reference = readback.get("auditReference") or ""
    try:
        audit_id = int(reference.rsplit(":", 1)[-1])
    except (TypeError, ValueError):
        audit_id = None
    return (
        OrganizationOperatingAuditRecord.objects.filter(
            pk=audit_id,
            action_code=REVIEW_ACTION,
            target_type=OBJECT_TYPE,
            target_id=version.pk,
        ).first()
        if audit_id else None
    )


def project_release_content_integrity(version, completeness=None):
    """Prove the released candidate is the exact content that passed review."""

    completeness = completeness or project_draft_completeness(version)
    current_snapshot = routing_version_content_snapshot(version, completeness)
    current_hash = content_hash(current_snapshot)
    audit = _review_audit(version)
    after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
    recorded_hash = after.get("reviewContentHash") or ""
    recorded_completeness = after.get("reviewCompleteness") or {}
    review_facts_match = bool(
        recorded_completeness
        and review_fact_snapshot(recorded_completeness) == review_fact_snapshot(completeness)
    )
    request = MasterDataWriteRequest.objects.filter(
        pk=review_readback(version).get("writeRequestId"),
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).first()
    watermark = request.updated_at if request else None
    latest_step_update = max(
        (row.updated_at for row in version.steps.all()),
        default=None,
    )
    no_post_review_write = bool(
        watermark
        and (not version.updated_at or version.updated_at <= watermark)
        and (not latest_step_update or latest_step_update <= watermark)
    )
    if recorded_hash:
        valid = recorded_hash == current_hash
        method = "REVIEW_CONTENT_HASH"
    else:
        valid = bool(audit and review_facts_match and no_post_review_write)
        method = "IMMUTABLE_REVIEWED_STATE_PLUS_RECORDED_FACTS"
    return {
        "valid": valid,
        "method": method,
        "currentContentHash": current_hash,
        "reviewContentHash": recorded_hash,
        "reviewAuditId": audit.pk if audit else None,
        "reviewFactsMatch": review_facts_match,
        "noPostReviewWrite": no_post_review_write,
        "reviewCommittedAt": watermark.isoformat() if watermark else "",
        "versionUpdatedAt": version.updated_at.isoformat() if version.updated_at else "",
        "latestStepUpdatedAt": latest_step_update.isoformat() if latest_step_update else "",
    }


def release_readback(version):
    transition = BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        action_code=RELEASE_ACTION,
        source_state="reviewed",
        target_state="released",
    ).select_related("operator", "workflow_instance").order_by("-version", "-pk").first()
    request = MasterDataWriteRequest.objects.filter(
        organization_id=_company_id(version),
        action_code=RELEASE_ACTION,
        entity_type=OBJECT_TYPE,
        target_entity_id=str(version.pk),
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).order_by("-pk").first()
    completed = bool(
        version.status == "released"
        and version.approval_state == APPROVED_PROJECTION
        and transition
        and request
    )
    return {
        "completed": completed,
        "statusCode": version.status,
        "statusLabel": version.get_status_display(),
        "actorId": transition.operator_id if transition else None,
        "actorUsername": transition.operator.username if transition else "",
        "actorRealName": transition.operator.real_name if transition else "",
        "releasedAt": transition.timestamp.isoformat() if transition else "",
        "businessStateTransitionId": transition.pk if transition else None,
        "auditReference": transition.audit_reference if transition else "",
        "workflowInstanceId": transition.workflow_instance_id if transition else None,
        "requestIdentity": request.idempotency_key if request else "",
        "writeRequestId": request.pk if request else None,
        "actionCode": RELEASE_ACTION,
    }


def project_release_preflight(version, user):
    completeness = project_draft_completeness(version)
    review = review_readback(version)
    integrity = project_release_content_integrity(version, completeness)
    permission_exists = Permission.objects.filter(code=RELEASE_PERMISSION).exists()
    responsibility_exists = Responsibility.objects.filter(
        code=REQUIRED_RESPONSIBILITY_CODE,
        is_active=True,
        status="ACTIVE",
    ).exists()
    actors = eligible_release_actors(_company_id(version), version.pk) if permission_exists else []
    current_actor = next((row for row in actors if row["userId"] == user.pk), None)
    reviewer_id = review.get("actorId")
    separated = bool(current_actor and reviewer_id and current_actor["userId"] != reviewer_id)
    readback = release_readback(version)
    gates = [
        _gate(
            "ROUTING_VERSION_FORMAL_IDENTITY",
            "工艺路线版本正式身份",
            bool(version.pk and version.routing_id and _company_id(version)),
            f"Routing {version.routing_id} / RoutingVersion {version.pk} / {version.routing_version} / Rev{version.revision}",
        ),
        _gate(
            "ROUTING_VERSION_REVIEWED_STATE",
            "当前版本状态",
            version.status == "reviewed",
            "当前版本处于已评审且尚未发布状态。" if version.status == "reviewed"
            else f"正式发布要求状态为reviewed，实际为{version.status}。",
        ),
        _gate(
            "FORMAL_REVIEW_APPROVED",
            "当前版本正式评审事实",
            bool(review.get("completed") and review.get("projectionConsistent")),
            (
                f"Workflow {review.get('workflowInstanceNo')} / Decision {review.get('decisionId')} / workflow_approved。"
                if review.get("completed") else "当前准确版本身份没有完整、唯一且一致的正式评审通过事实。"
            ),
            review,
        ),
        _gate(
            "REVIEWED_CONTENT_UNCHANGED",
            "评审后内容未失效",
            integrity["valid"],
            "当前版本内容与正式评审事实一致，且评审后没有合法内容写入。"
            if integrity["valid"] else "当前版本内容无法证明与正式评审时完全一致。",
            integrity,
        ),
        _gate(
            "RELEASE_COMPLETENESS_VALID",
            "工序完整性与适用性结论",
            bool(completeness.get("complete")),
            (
                f"{completeness.get('stepCount', 0)}道工序及适用性结论仍全部有效。"
                if completeness.get("complete") else "工序完整性或适用性结论已经失效。"
            ),
        ),
        _gate(
            "RELEASE_PERMISSION_REGISTERED",
            "专用正式发布权限",
            permission_exists,
            f"已登记{RELEASE_PERMISSION}。" if permission_exists else f"尚未登记{RELEASE_PERMISSION}。",
        ),
        _gate(
            "RELEASE_RESPONSIBILITY_REGISTERED",
            "专用正式发布职责",
            responsibility_exists,
            f"已登记{REQUIRED_RESPONSIBILITY_CODE}。" if responsibility_exists
            else f"尚未由组织权限管理任命{REQUIRED_RESPONSIBILITY_CODE}职责。",
        ),
        _gate(
            "FORMAL_RELEASE_ACTOR_APPOINTED",
            "正式发布人任命",
            bool(actors),
            f"已解析{len(actors)}名完整合法发布人。" if actors
            else "COMP001尚无同时具备专用角色、权限、岗位职责、正式员工账号及有效Scope的发布人。",
        ),
        _gate(
            "CURRENT_ACTOR_AUTHORIZED",
            "当前操作人发布资格",
            bool(current_actor),
            (
                f"{current_actor['realName']} / {current_actor['username']} / "
                f"{current_actor['positionCode']} / ORGANIZATION:{_company_id(version)}"
                if current_actor else
                f"当前账号未通过{RELEASE_PERMISSION}专用发布责任链。"
            ),
        ),
        _gate(
            "REVIEW_RELEASE_DUTY_SEPARATION",
            "评审与发布职责分离",
            separated,
            "发布人与正式评审人是不同账号。" if separated else "发布人必须与当前版本正式评审人分离。",
            {"reviewerUserId": reviewer_id, "publisherUserId": current_actor.get("userId") if current_actor else None},
        ),
        _gate(
            "NOT_ALREADY_RELEASED",
            "重复发布保护",
            not readback["completed"],
            "当前版本尚无正式发布事实。" if not readback["completed"] else "当前版本已经正式发布，不得重复形成发布事实。",
        ),
    ]
    first_blocker = next((row for row in gates if row["statusCode"] != "PASS"), None)
    release_allowed = bool(version.status == "reviewed" and not first_blocker)
    human_authorization_required = bool(
        version.status == "reviewed"
        and review.get("completed")
        and integrity["valid"]
        and completeness.get("complete")
        and permission_exists
        and not actors
    )
    return {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": RELEASE_ACTION,
        "permissionCode": RELEASE_PERMISSION,
        "requiredResponsibilityCode": REQUIRED_RESPONSIBILITY_CODE,
        "targetStatusCode": "released",
        "targetStatusLabel": "已发布",
        "releaseAllowed": release_allowed,
        "humanPublisherAuthorizationRequired": human_authorization_required,
        "decisionCode": (
            "PASS_READY_FOR_HUMAN_RELEASE" if release_allowed else
            "PASS_FORMAL_RELEASE_COMPLETE" if readback["completed"] else
            "HUMAN_PUBLISHER_AUTHORIZATION_REQUIRED" if human_authorization_required else
            "BLOCKED"
        ),
        "decisionLabel": (
            "允许正式发布" if release_allowed else
            "正式发布已完成" if readback["completed"] else
            "需要任命正式发布人" if human_authorization_required else
            "暂不可正式发布"
        ),
        "firstBlockerCode": first_blocker["code"] if first_blocker else "",
        "firstBlockerLabel": first_blocker["label"] if first_blocker else "",
        "firstBlockerMessage": first_blocker["evidence"] if first_blocker else "",
        "gates": gates,
        "gatePassCount": sum(row["statusCode"] == "PASS" for row in gates),
        "gateFailCount": sum(row["statusCode"] != "PASS" for row in gates),
        "eligibleReleaseActors": actors,
        "currentActor": current_actor or {},
        "reviewReadback": review,
        "contentIntegrity": integrity,
        "completeness": completeness,
        "releaseReadback": readback,
    }


def _require_actor(version, user):
    actor = next(
        (row for row in eligible_release_actors(_company_id(version), version.pk) if row["userId"] == user.pk),
        None,
    )
    if not actor:
        raise RoutingVersionReleaseError(
            "PERMISSION_DENIED",
            "当前登录人员不具备工艺路线版本专用发布角色、范围、员工、岗位与职责资格。",
            403,
            {
                "permissionCode": RELEASE_PERMISSION,
                "requiredResponsibilityCode": REQUIRED_RESPONSIBILITY_CODE,
            },
        )
    return actor


def _reserve_request(*, version, user, reason, key):
    key = str(key or "").strip()
    if not key:
        raise RoutingVersionReleaseError("IDEMPOTENCY_KEY_REQUIRED", "正式发布必须提供Idempotency-Key。", 409)
    payload = {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": RELEASE_ACTION,
        "routingVersionId": version.pk,
        "targetState": "released",
        "actorId": user.pk,
        "reason": reason,
    }
    request_hash = _hash(payload)
    existing = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=_company_id(version),
        action_code=RELEASE_ACTION,
        idempotency_key=key,
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise RoutingVersionReleaseError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同工艺路线版本发布payload。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise RoutingVersionReleaseError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity已有未完成的工艺路线版本发布。",
            409,
        )
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=_company_id(version),
        source_system="PCE_ROUTING_VERSION_RELEASE",
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
        raise RoutingVersionReleaseError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "现有ExternalIdentity与当前工艺路线版本范围不一致。",
            409,
        )
    return MasterDataWriteRequest.objects.create(
        organization_id=_company_id(version),
        action_code=RELEASE_ACTION,
        entity_type=OBJECT_TYPE,
        idempotency_key=key,
        request_hash=request_hash,
        source_identity=identity,
        audit_metadata=payload,
    ), False


def _commit_request(request, result, version):
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(version.pk)
    request.result = result
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])


@transaction.atomic
def release_routing_version(*, object_id, user, reason, idempotency_key, action=""):
    reason = str(reason or "").strip()
    if not reason:
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_RELEASE_REASON_REQUIRED", "正式发布说明必须填写。", 422,
        )
    if action and str(action).strip() != RELEASE_ACTION:
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_RELEASE_ACTION_CONFLICT",
            "请求action与工艺路线版本专用正式发布动作不一致。",
            409,
        )
    version = RoutingVersion.objects.select_for_update().select_related(
        "routing", "routing__company", "product", "product__company",
    ).filter(pk=object_id).first()
    if not version:
        raise RoutingVersionReleaseError("ROUTING_VERSION_NOT_FOUND", "待发布工艺路线版本不存在。", 404)
    if version.usage_purpose == 'TEST_BUSINESS':
        raise RoutingVersionReleaseError('TEST_ROUTE_FORMAL_USE_DENIED', '测试路线草稿禁止正式评审、发布和制造承接。', 409)
    if _company_id(version) != user.company_id:
        raise RoutingVersionReleaseError(
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
    if version.status != "reviewed":
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_STATE_CONFLICT",
            f"正式发布要求当前状态为reviewed，实际为{version.status}。",
            409,
        )
    authorization = _require_actor(version, user)
    review = review_readback(version)
    if not review.get("completed") or not review.get("projectionConsistent"):
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_FORMAL_REVIEW_REQUIRED",
            "当前准确版本身份没有完整、唯一且一致的正式评审通过事实。",
            422,
        )
    if review.get("actorId") == user.pk:
        raise RoutingVersionReleaseError(
            "REVIEW_RELEASE_DUTY_SEPARATION_REQUIRED",
            "正式发布人必须与当前版本正式评审人分离。",
            403,
        )
    completeness = project_draft_completeness(version)
    if not completeness.get("complete"):
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_RELEASE_GATE_BLOCKED",
            "工序完整性或适用性结论已经失效。",
            422,
            {"failedGates": [row for row in completeness.get("gates", []) if row.get("statusCode") != "PASS"]},
        )
    integrity = project_release_content_integrity(version, completeness)
    if not integrity["valid"]:
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_REVIEW_CONTENT_INVALIDATED",
            "当前版本内容无法证明与正式评审时完全一致。",
            409,
            integrity,
        )
    if BusinessStateTransition.objects.select_for_update().filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        action_code=RELEASE_ACTION,
        target_state="released",
    ).exists():
        raise RoutingVersionReleaseError(
            "ROUTING_VERSION_ALREADY_RELEASED",
            "该工艺路线版本已经形成正式发布事实，不得重复发布。",
            409,
        )
    workflow_id = review.get("workflowInstanceId")
    before = _snapshot(version)
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=RELEASE_ACTION,
        actor=user,
        organization_id=_company_id(version),
        target_type=OBJECT_TYPE,
        target_id=version.pk,
        target_label=f"{version.routing_version} / Rev{version.revision}",
        reason=reason,
        before_snapshot=before,
        after_snapshot={
            **before,
            "status": "released",
            "approvalState": APPROVED_PROJECTION,
            "reviewWorkflowInstanceId": workflow_id,
            "reviewDecisionId": review.get("decisionId"),
            "reviewActorId": review.get("actorId"),
            "requestIdentity": str(idempotency_key).strip(),
            "authorization": authorization,
            "releaseContentHash": integrity["currentContentHash"],
            "contentIntegrity": integrity,
            "releaseCompleteness": completeness,
            "controlContract": CONTROL_CONTRACT,
        },
    )
    workflow_instance = WorkflowInstance.objects.filter(pk=workflow_id).first()
    transition = transition_business_object(
        business_object=version,
        object_type=OBJECT_TYPE,
        source_state="reviewed",
        target_state="released",
        action_code=RELEASE_ACTION,
        operator=user,
        reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        workflow_instance=workflow_instance,
        allowed_transitions=ALLOWED_TRANSITIONS,
        version_field=None,
    )
    result = {
        "contractVersion": CONTROL_CONTRACT,
        "idempotentReplay": False,
        "routingVersion": _snapshot(version),
        "review": review,
        "contentIntegrity": integrity,
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
    "CONTROL_CONTRACT",
    "RELEASE_ACTION",
    "RELEASE_PERMISSION",
    "REQUIRED_RESPONSIBILITY_CODE",
    "RoutingVersionReleaseError",
    "eligible_release_actors",
    "project_release_content_integrity",
    "project_release_preflight",
    "release_readback",
    "release_routing_version",
]
