"""Formal ``reviewed -> released`` control for EngineeringDocumentVersion.

The release reuses the existing ``production.engineering.document.release``
permission and organization responsibility chain.  It does not create another
approval workflow and it never creates or advances ProductManufacturingOutput.
"""

from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from copy import deepcopy
from hashlib import sha256
import json

from django.core.exceptions import ValidationError
from django.db import transaction
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
from workflow_runtime.models import BusinessStateTransition, WorkflowInstance
from workflow_runtime.state_transitions import transition_business_object

from .engineering_document_version_review_service import (
    APPROVED_PROJECTION,
    OBJECT_TYPE,
    REVIEW_ACTION,
    _content_snapshot,
    review_readback,
)
from .models import EngineeringDocument, EngineeringDocumentVersion


CONTROL_CONTRACT = "PCE-ENGINEERING-DOCUMENT-VERSION-FORMAL-RELEASE-V1.0"
RELEASE_ACTION = "production.engineering.document.release"
RELEASE_PERMISSION = RELEASE_ACTION
ALLOWED_TRANSITIONS = (("reviewed", "released"),)
RELEASE_SOURCE_SYSTEM = "PCE_ENGINEERING_DOCUMENT_VERSION_RELEASE"


class EngineeringDocumentVersionReleaseError(ValueError):
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
    if version.order_engineering_instance_id:
        return version.order_engineering_instance.company_id
    if version.related_product_id:
        return version.related_product.company_id
    return None


def _snapshot(version):
    return {
        "engineeringDocumentVersionId": version.pk,
        "engineeringDocumentId": version.document_id,
        "documentNo": version.document.document_no,
        "documentName": version.document_name,
        "documentVersion": version.document_version,
        "status": version.status,
        "approvalState": APPROVED_PROJECTION,
        "releaseSubjectType": version.release_subject_type,
        "companyId": _company_id(version),
        "orderEngineeringInstanceId": version.order_engineering_instance_id,
        "orderEngineeringBaselineId": version.order_engineering_baseline_id,
        "engineeringCalculationId": version.engineering_calculation_id,
        "bomVersionId": version.related_bom_id,
        "routingVersionId": version.related_routing_id,
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


def _stable_review_snapshot(snapshot):
    """Exclude only lifecycle fields that the review transition itself changes."""

    value = deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    value.pop("status", None)
    value.pop("updatedAt", None)
    return value


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


def project_release_content_integrity(version):
    """Compare the current exact source graph with the snapshot approved at review."""

    audit = _review_audit(version)
    after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
    recorded_snapshot = after.get("reviewContentSnapshot") or {}
    recorded_hash = after.get("reviewContentHash") or ""
    current_snapshot = _content_snapshot(version)
    recorded_snapshot_hash = _hash(recorded_snapshot) if recorded_snapshot else ""
    stable_recorded_hash = _hash(_stable_review_snapshot(recorded_snapshot)) if recorded_snapshot else ""
    stable_current_hash = _hash(_stable_review_snapshot(current_snapshot))
    recorded_snapshot_untampered = bool(
        recorded_snapshot and recorded_hash and recorded_snapshot_hash == recorded_hash
    )
    stable_content_match = bool(
        recorded_snapshot and stable_recorded_hash == stable_current_hash
    )
    return {
        "valid": bool(audit and recorded_snapshot_untampered and stable_content_match),
        "method": "REVIEW_SNAPSHOT_STABLE_CONTENT_FIELDS",
        "reviewAuditId": audit.pk if audit else None,
        "reviewContentHash": recorded_hash,
        "recordedSnapshotHash": recorded_snapshot_hash,
        "stableReviewContentHash": stable_recorded_hash,
        "stableCurrentContentHash": stable_current_hash,
        "recordedSnapshotUntampered": recorded_snapshot_untampered,
        "stableContentMatch": stable_content_match,
        "excludedLifecycleFields": ["status", "updatedAt"],
    }


def project_release_source_completeness(version):
    gates = []
    company_id = _company_id(version)
    identity_ready = bool(
        version.pk and version.document_id and company_id and version.document_version
    )
    gates.append(_gate(
        "ENGINEERING_DOCUMENT_VERSION_FORMAL_IDENTITY",
        "工程资料版本正式身份",
        identity_ready,
        (
            f"EngineeringDocument {version.document_id} / EngineeringDocumentVersion "
            f"{version.pk} / {version.document_version} / COMP{company_id}"
            if identity_ready else "工程资料版本缺少主表、公司或版本身份。"
        ),
    ))

    relation_valid = True
    relation_error = ""
    try:
        version.full_clean()
    except ValidationError as exc:
        relation_valid = False
        relation_error = str(exc)
    gates.append(_gate(
        "ENGINEERING_DOCUMENT_VERSION_RELATION_CONTRACT",
        "精确来源关系合同",
        relation_valid,
        "工程资料版本模型及精确外键关系校验通过。" if relation_valid else relation_error,
    ))

    bom_ready = bool(version.related_bom_id and version.related_bom.status == "released")
    gates.append(_gate(
        "RELEASED_BOM_VERSION",
        "已发布BOM版本",
        bom_ready,
        (
            f"BOMVersion {version.related_bom_id} / {version.related_bom.bom_version} / released"
            if bom_ready else "关联BOMVersion不是已发布状态。"
        ),
    ))

    routing_step_count = version.related_routing.steps.count() if version.related_routing_id else 0
    routing_ready = bool(
        version.related_routing_id
        and version.related_routing.status == "released"
        and routing_step_count > 0
    )
    gates.append(_gate(
        "RELEASED_ROUTING_VERSION",
        "已发布工艺路线版本",
        routing_ready,
        (
            f"RoutingVersion {version.related_routing_id} / "
            f"{version.related_routing.routing_version} / Rev{version.related_routing.revision} / "
            f"released / {routing_step_count}道工序"
            if routing_ready else "关联RoutingVersion未发布或没有正式工序。"
        ),
    ))

    order_specific = version.release_subject_type == "ORDER_ENGINEERED_PRODUCT"
    if order_specific:
        baseline_ready = bool(
            version.order_engineering_baseline_id
            and production_status(version.order_engineering_baseline) == "confirmed"
        )
        calculation_ready = bool(
            version.engineering_calculation_id
            and version.engineering_calculation.status == "completed"
        )
        instance_ready = bool(
            version.order_engineering_instance_id
            and version.order_engineering_instance.status != "inactive"
        )
    else:
        baseline_ready = calculation_ready = instance_ready = True
    gates.extend([
        _gate(
            "ORDER_ENGINEERING_INSTANCE_VALID",
            "订单工程实例",
            instance_ready,
            (
                f"OrderEngineeringInstance {version.order_engineering_instance_id}有效。"
                if order_specific and instance_ready else
                "长期产品资料版本不适用订单工程实例Gate。"
                if not order_specific else "订单工程实例缺失或已失效。"
            ),
        ),
        _gate(
            "CONFIRMED_ENGINEERING_BASELINE",
            "已确认工程基线",
            baseline_ready,
            (
                f"EngineeringBaseline {version.order_engineering_baseline_id} / confirmed"
                if order_specific and baseline_ready else
                "长期产品资料版本不适用工程基线Gate。"
                if not order_specific else "工程基线缺失或未确认。"
            ),
        ),
        _gate(
            "COMPLETED_ENGINEERING_CALCULATION",
            "已完成工程核算",
            calculation_ready,
            (
                f"EngineeringCalculation {version.engineering_calculation_id} / completed"
                if order_specific and calculation_ready else
                "长期产品资料版本不适用工程核算Gate。"
                if not order_specific else "工程核算缺失或未完成。"
            ),
        ),
    ])
    return {
        "complete": all(row["statusCode"] == "PASS" for row in gates),
        "gates": gates,
        "routingStepCount": routing_step_count,
        "manufacturingOutputCount": version.manufacturing_outputs.count(),
        "exactChain": {
            "engineeringDocumentVersionId": version.pk,
            "orderEngineeringInstanceId": version.order_engineering_instance_id,
            "orderEngineeringBaselineId": version.order_engineering_baseline_id,
            "engineeringCalculationId": version.engineering_calculation_id,
            "bomVersionId": version.related_bom_id,
            "routingVersionId": version.related_routing_id,
        },
    }


def eligible_release_actors(version):
    """Resolve Permission -> Role/Scope -> Employee -> Position -> Responsibility."""

    company_id = _company_id(version)
    permission = Permission.objects.filter(code=RELEASE_PERMISSION).first()
    if not permission or not company_id:
        return []
    role_permissions = list(
        RolePermission.objects.filter(permission=permission)
        .select_related("role")
        .order_by("pk")
    )
    role_ids = {row.role_id for row in role_permissions}
    role_permission_by_role = {row.role_id: row for row in role_permissions}
    assignments = list(
        UserRoleScopeAssignment.objects.filter(
            organization_id=company_id,
            role_id__in=role_ids,
            scope_code__in=(
                UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
                UserRoleScopeAssignment.ScopeCode.ALL,
            ),
            active=True,
            user__is_active=True,
            user__is_superuser=False,
        ).select_related("role", "user").order_by("pk")
    )
    assignments_by_user = {}
    for assignment in assignments:
        assignments_by_user.setdefault(assignment.user_id, []).append(assignment)
    employees = {
        row.user_id: row
        for row in formal_employee_queryset(
            Employee.objects.select_related("department_ref", "position_ref"),
            company_id=company_id,
        ).filter(user_id__in=assignments_by_user)
    }
    rows = []
    for user in User.objects.filter(pk__in=employees, is_superuser=False).order_by("pk"):
        employee = employees[user.pk]
        position = employee.position_ref
        mappings = list(
            PositionResponsibility.objects.filter(
                position=position,
                active=True,
                responsibility__is_active=True,
                responsibility__status="ACTIVE",
            ).select_related("responsibility").order_by("pk")
        )
        if not mappings:
            continue
        decision = AuthorizationService.decide(
            user=user,
            action_code=RELEASE_PERMISSION,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "entity": "engineering-document-versions",
                "id": version.pk,
            },
            context={"moduleCode": "PDE", "businessWrite": True},
        )
        if not decision.get("allowed"):
            continue
        user_assignments = assignments_by_user[user.pk]
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "departmentId": employee.department_ref_id,
            "departmentCode": employee.department_ref.code,
            "departmentName": employee.department_ref.name,
            "positionId": position.pk,
            "positionCode": position.code,
            "positionName": position.name,
            "roleIds": sorted({row.role_id for row in user_assignments}),
            "matchedRoleCodes": sorted({row.role.code for row in user_assignments}),
            "rolePermissionIds": sorted({
                role_permission_by_role[row.role_id].pk for row in user_assignments
            }),
            "userRoleScopeAssignmentIds": [row.pk for row in user_assignments],
            "scopeCodes": sorted({row.scope_code for row in user_assignments}),
            "positionResponsibilityIds": [row.pk for row in mappings],
            "responsibilityCodes": [row.responsibility.code for row in mappings],
            "authorizationDecisionCode": decision.get("decisionCode", ""),
        })
    return rows


def release_readback(version, *, read_cache=None):
    from .operation_requirement_service import _ReadOnlyProofCache, _requirement_read_cache, _read_guarded_raw
    cache = (_requirement_read_cache(read_cache, _company_id(version))
        if isinstance(read_cache, _ReadOnlyProofCache) else None)

    def raw(key, loader):
        return _read_guarded_raw(cache, ('engineering_document_release_readback', version.pk, *key), loader)

    transition = raw(('transition', OBJECT_TYPE, RELEASE_ACTION, 'reviewed', 'released'), lambda:
        BusinessStateTransition.objects.filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        action_code=RELEASE_ACTION,
        source_state="reviewed",
        target_state="released",
    ).select_related("operator").only(
        *(field.attname for field in BusinessStateTransition._meta.concrete_fields),
        "operator__id", "operator__username", "operator__real_name",
    ).order_by("-version", "-pk").first())
    request = raw(('request', _company_id(version), RELEASE_ACTION, OBJECT_TYPE, str(version.pk), 'COMMITTED'), lambda:
        MasterDataWriteRequest.objects.filter(
        organization_id=_company_id(version),
        action_code=RELEASE_ACTION,
        entity_type=OBJECT_TYPE,
        target_entity_id=str(version.pk),
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).order_by("-pk").first())
    audit = None
    if transition and transition.audit_reference:
        try:
            audit_id = int(transition.audit_reference.rsplit(":", 1)[-1])
        except (TypeError, ValueError):
            audit_id = None
        audit = raw(('audit', audit_id, RELEASE_ACTION, OBJECT_TYPE, version.pk), lambda:
            OrganizationOperatingAuditRecord.objects.filter(
            pk=audit_id,
            action_code=RELEASE_ACTION,
            target_type=OBJECT_TYPE,
            target_id=version.pk,
        ).first()) if audit_id else None
    completed = bool(
        version.status == "released"
        and review_readback(version).get("completed")
        and transition and request and audit
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
        "auditId": audit.pk if audit else None,
        "auditReference": transition.audit_reference if transition else "",
        "workflowInstanceId": transition.workflow_instance_id if transition else None,
        "requestIdentity": request.idempotency_key if request else "",
        "writeRequestId": request.pk if request else None,
        "actionCode": RELEASE_ACTION,
        "manufacturingReleaseExecuted": False,
    }


def project_release_preflight(version, user):
    review = review_readback(version)
    integrity = project_release_content_integrity(version)
    completeness = project_release_source_completeness(version)
    permission_exists = Permission.objects.filter(code=RELEASE_PERMISSION).exists()
    actors = eligible_release_actors(version) if permission_exists else []
    separated_actors = [row for row in actors if row["userId"] != review.get("actorId")]
    current_actor = next((row for row in actors if row["userId"] == getattr(user, "pk", None)), None)
    current_actor_separated = bool(
        current_actor and current_actor["userId"] != review.get("actorId")
    )
    readback = release_readback(version)
    system_gates = [
        _gate(
            "ENGINEERING_DOCUMENT_VERSION_REVIEWED_STATE",
            "当前版本状态",
            version.status == "reviewed",
            "当前版本为已评审且尚未发布。" if version.status == "reviewed"
            else f"正式发布要求reviewed，实际为{version.status}。",
        ),
        _gate(
            "FORMAL_REVIEW_APPROVED",
            "正式评审决定",
            bool(review.get("completed") and review.get("projectionConsistent")),
            (
                f"Workflow {review.get('workflowInstanceId')} / Decision "
                f"{review.get('decisionId')} / workflow_approved"
                if review.get("completed") else "当前准确版本没有完整一致的正式评审事实。"
            ),
            review,
        ),
        _gate(
            "REVIEWED_CONTENT_UNCHANGED",
            "评审后内容未失效",
            integrity["valid"],
            "当前精确来源内容与正式评审快照一致。"
            if integrity["valid"] else "无法证明当前内容与正式评审快照一致。",
            integrity,
        ),
        *completeness["gates"],
        _gate(
            "DOCUMENT_RELEASE_PERMISSION_REGISTERED",
            "工程资料版本发布权限",
            permission_exists,
            f"已登记{RELEASE_PERMISSION}。" if permission_exists
            else f"尚未登记{RELEASE_PERMISSION}。",
        ),
        _gate(
            "FORMAL_DOCUMENT_PUBLISHER_APPOINTED",
            "正式发布人员",
            bool(separated_actors),
            f"已解析{len(separated_actors)}名与评审人分离的合法发布人员。"
            if separated_actors else "COMP001没有与评审人分离的完整合法发布人员。",
        ),
        _gate(
            "NOT_ALREADY_RELEASED",
            "重复发布保护",
            not readback["completed"],
            "当前版本尚无正式发布事实。" if not readback["completed"]
            else "当前版本已经正式发布。",
        ),
    ]
    first_blocker = next((row for row in system_gates if row["statusCode"] != "PASS"), None)
    ready = bool(version.status == "reviewed" and not first_blocker)
    current_browser_operable = bool(ready and current_actor and current_actor_separated)
    current_actor_gate = _gate(
        "CURRENT_ACTOR_AUTHORIZED_AND_SEPARATED",
        "当前操作人发布资格",
        current_browser_operable,
        (
            f"{current_actor['realName']} / {current_actor['username']} / "
            f"{current_actor['positionCode']} / ORGANIZATION:{_company_id(version)}"
            if current_browser_operable else
            "当前浏览器账号不是与评审人分离的合法工程资料版本发布人员。"
        ),
        {
            "reviewerUserId": review.get("actorId"),
            "publisherUserId": current_actor.get("userId") if current_actor else None,
        },
    )
    human_authorization_required = bool(
        version.status == "reviewed"
        and review.get("completed")
        and integrity["valid"]
        and completeness["complete"]
        and permission_exists
        and not separated_actors
    )
    if readback["completed"]:
        decision_code = "PASS_FORMAL_DOCUMENT_RELEASE_COMPLETE"
        decision_label = "工程资料版本正式发布已完成"
    elif ready:
        decision_code = "PASS_READY_FOR_HUMAN_DOCUMENT_RELEASE"
        decision_label = "工程资料版本正式发布准入通过"
    elif human_authorization_required:
        decision_code = "HUMAN_DOCUMENT_PUBLISHER_AUTHORIZATION_REQUIRED"
        decision_label = "需要任命工程资料版本正式发布人员"
    else:
        decision_code = "BLOCKED"
        decision_label = "工程资料版本正式发布暂不可执行"
    return {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": RELEASE_ACTION,
        "permissionCode": RELEASE_PERMISSION,
        "targetStatusCode": "released",
        "targetStatusLabel": "已发布",
        "readyForHumanRelease": ready,
        "releaseAllowed": current_browser_operable,
        "currentBrowserOperable": current_browser_operable,
        "humanPublisherAuthorizationRequired": human_authorization_required,
        "decisionCode": decision_code,
        "decisionLabel": decision_label,
        "firstBlockerCode": first_blocker["code"] if first_blocker else "",
        "firstBlockerLabel": first_blocker["label"] if first_blocker else "",
        "firstBlockerMessage": first_blocker["evidence"] if first_blocker else "",
        "gates": system_gates,
        "currentActorGate": current_actor_gate,
        "gatePassCount": sum(row["statusCode"] == "PASS" for row in system_gates),
        "gateFailCount": sum(row["statusCode"] != "PASS" for row in system_gates),
        "eligibleReleaseActors": separated_actors,
        "currentActor": current_actor or {},
        "currentUser": {
            "userId": getattr(user, "pk", None),
            "username": getattr(user, "username", ""),
            "realName": getattr(user, "real_name", ""),
        },
        "reviewReadback": review,
        "contentIntegrity": integrity,
        "sourceCompleteness": completeness,
        "releaseReadback": readback,
        "manufacturingReleaseRequired": False,
        "manufacturingReleaseExecuted": False,
        "databaseBusinessWriteCount": 0,
    }


def _require_actor(version, user):
    actor = next(
        (row for row in eligible_release_actors(version) if row["userId"] == user.pk),
        None,
    )
    if not actor:
        raise EngineeringDocumentVersionReleaseError(
            "PERMISSION_DENIED",
            "当前登录人员不具备工程资料版本发布所需的角色、权限、Scope、正式员工、岗位与职责链。",
            403,
            {"permissionCode": RELEASE_PERMISSION},
        )
    return actor


def _reserve_request(*, version, user, reason, key):
    key = str(key or "").strip()
    if not key:
        raise EngineeringDocumentVersionReleaseError(
            "IDEMPOTENCY_KEY_REQUIRED", "正式发布必须提供Idempotency-Key。", 409,
        )
    payload = {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": RELEASE_ACTION,
        "engineeringDocumentVersionId": version.pk,
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
            raise EngineeringDocumentVersionReleaseError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同工程资料版本发布payload。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise EngineeringDocumentVersionReleaseError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity已有未完成的工程资料版本发布。",
            409,
        )
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=_company_id(version),
        source_system=RELEASE_SOURCE_SYSTEM,
        source_type="BUSINESS_ACTION_SCOPE",
        source_object_type=OBJECT_TYPE,
        external_id=f"EngineeringDocumentVersion:{version.pk}",
        defaults={
            "target_entity_type": OBJECT_TYPE,
            "target_entity_id": str(version.pk),
            "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": _hash({"objectType": OBJECT_TYPE, "objectId": version.pk}),
            "audit_metadata": {"contractVersion": CONTROL_CONTRACT},
        },
    )
    if identity.target_entity_type != OBJECT_TYPE or identity.target_entity_id != str(version.pk):
        raise EngineeringDocumentVersionReleaseError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "现有ExternalIdentity与当前工程资料版本范围不一致。",
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


@transaction.atomic
def release_engineering_document_version(*, object_id, user, reason, idempotency_key, action=""):
    reason = str(reason or "").strip()
    if not reason:
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_RELEASE_REASON_REQUIRED",
            "正式发布说明必须填写。",
            422,
        )
    if action and str(action).strip() != RELEASE_ACTION:
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_RELEASE_ACTION_CONFLICT",
            "请求action与工程资料版本正式发布动作不一致。",
            409,
        )
    version = EngineeringDocumentVersion.objects.select_for_update().select_related(
        "document", "related_product", "order_engineering_instance__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "order_engineering_baseline", "engineering_calculation",
        "related_bom__bom", "related_routing__routing",
    ).filter(pk=object_id).first()
    if not version:
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_NOT_FOUND", "待发布工程资料版本不存在。", 404,
        )
    if _company_id(version) != user.company_id:
        raise EngineeringDocumentVersionReleaseError(
            "SCOPE_DENIED", "工程资料版本不属于当前登录用户的正式组织范围。", 403,
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
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_STATE_CONFLICT",
            f"正式发布要求当前状态为reviewed，实际为{version.status}。",
            409,
        )
    authorization = _require_actor(version, user)
    review = review_readback(version)
    if not review.get("completed") or not review.get("projectionConsistent"):
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_FORMAL_REVIEW_REQUIRED",
            "当前准确版本身份没有完整一致的正式评审通过事实。",
            422,
        )
    if review.get("actorId") == user.pk:
        raise EngineeringDocumentVersionReleaseError(
            "REVIEW_RELEASE_DUTY_SEPARATION_REQUIRED",
            "工程资料版本正式发布人必须与正式评审人分离。",
            403,
        )
    completeness = project_release_source_completeness(version)
    if not completeness["complete"]:
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_RELEASE_GATE_BLOCKED",
            "工程资料版本精确来源链未通过全部发布Gate。",
            422,
            {"failedGates": [
                row for row in completeness["gates"] if row["statusCode"] != "PASS"
            ]},
        )
    integrity = project_release_content_integrity(version)
    if not integrity["valid"]:
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_CONTENT_INVALIDATED",
            "当前工程资料版本内容无法证明与正式评审时一致。",
            409,
            integrity,
        )
    if BusinessStateTransition.objects.select_for_update().filter(
        object_type=OBJECT_TYPE,
        object_id=version.pk,
        action_code=RELEASE_ACTION,
        target_state="released",
    ).exists():
        raise EngineeringDocumentVersionReleaseError(
            "ENGINEERING_DOCUMENT_VERSION_ALREADY_RELEASED",
            "该工程资料版本已经形成正式发布事实，不得重复发布。",
            409,
        )

    workflow_instance = WorkflowInstance.objects.filter(
        pk=review.get("workflowInstanceId"),
    ).first()
    before = _snapshot(version)
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=RELEASE_ACTION,
        actor=user,
        organization_id=_company_id(version),
        target_type=OBJECT_TYPE,
        target_id=version.pk,
        target_label=f"{version.document.document_no} / {version.document_version}",
        reason=reason,
        before_snapshot=before,
        after_snapshot={
            **before,
            "status": "released",
            "approvalState": APPROVED_PROJECTION,
            "reviewWorkflowInstanceId": review.get("workflowInstanceId"),
            "reviewDecisionId": review.get("decisionId"),
            "reviewActorId": review.get("actorId"),
            "requestIdentity": str(idempotency_key).strip(),
            "authorization": authorization,
            "contentIntegrity": integrity,
            "sourceCompleteness": completeness,
            "manufacturingReleaseExecuted": False,
            "controlContract": CONTROL_CONTRACT,
        },
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
        workflow_instance=workflow_instance,
        allowed_transitions=ALLOWED_TRANSITIONS,
        version_field=None,
    )
    EngineeringDocument.objects.filter(pk=version.document_id).update(
        version=version.document_version,
    )
    version.document.version = version.document_version
    result = {
        "contractVersion": CONTROL_CONTRACT,
        "idempotentReplay": False,
        "engineeringDocumentVersion": _snapshot(version),
        "review": review,
        "contentIntegrity": integrity,
        "sourceCompleteness": completeness,
        "publisher": authorization,
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
        "manufacturingReleaseExecuted": False,
        "manufacturingOutputCount": version.manufacturing_outputs.count(),
    }
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(version.pk)
    request.result = result
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return result


__all__ = [
    "ALLOWED_TRANSITIONS",
    "CONTROL_CONTRACT",
    "RELEASE_ACTION",
    "RELEASE_PERMISSION",
    "EngineeringDocumentVersionReleaseError",
    "eligible_release_actors",
    "project_release_content_integrity",
    "project_release_preflight",
    "project_release_source_completeness",
    "release_engineering_document_version",
    "release_readback",
]
