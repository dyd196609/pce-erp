"""Formal EngineeringDocumentVersion review on the shared PCE ledgers.

This adapter owns only ``draft -> reviewed``.  It reuses the existing Workflow
Runtime, BusinessStateTransition, audit and idempotency models.  It does not
publish an engineering document, create a manufacturing output, or grant any
personnel authority.
"""

from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from datetime import date
from hashlib import sha256
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    PositionWorkflowResponsibility,
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

from .engineering_document_version_workflow_catalog import CANONICAL_DEFINITION
from .models import EngineeringDocumentVersion, ProductManufacturingOutput
from .order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationError,
    OrderEngineeringDocumentRegistrationService,
)


CONTROL_CONTRACT = "PCE-ENGINEERING-DOCUMENT-VERSION-FORMAL-REVIEW-V1.0"
DOCUMENT_TYPE = "EngineeringDocumentVersion"
WORKFLOW_DOCUMENT_TYPES = (
    DOCUMENT_TYPE,
    "pde.EngineeringDocumentVersion",
    "engineering-document-versions",
)
OBJECT_TYPE = DOCUMENT_TYPE
REVIEW_ACTION = "pde.engineering_document_version.review"
REVIEW_PERMISSION = REVIEW_ACTION
APPROVED_PROJECTION = "workflow_approved"
ALLOWED_TRANSITIONS = (("draft", "reviewed"),)


class EngineeringDocumentVersionReviewError(ValueError):
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


def _json_safe(value):
    """Normalize persisted snapshots with Django's standard JSON semantics."""

    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False))


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
        "documentType": version.document.document_type,
        "documentVersion": version.document_version,
        "status": version.status,
        "releaseSubjectType": version.release_subject_type,
        "companyId": _company_id(version),
        "orderEngineeringInstanceId": version.order_engineering_instance_id,
        "orderEngineeringBaselineId": version.order_engineering_baseline_id,
        "engineeringCalculationId": version.engineering_calculation_id,
        "bomVersionId": version.related_bom_id,
        "routingVersionId": version.related_routing_id,
        "updatedAt": version.updated_at.isoformat() if version.updated_at else "",
    }


def _content_snapshot(version):
    steps = list(
        version.related_routing.steps.select_related("operation")
        .order_by("sequence", "pk")
        .values(
            "id", "sequence", "operation_id", "operation__code",
            "workshop_id", "work_center_id", "applies_to_item_id",
            "standard_hours", "setup_hours", "transfer_hours",
            "quality_checkpoint", "instruction", "operation_parameters",
            "predecessor_sequences", "effective_transition_mode",
            "resource_selection_rule", "is_active",
        )
    )
    return _json_safe({
        **_snapshot(version),
        "documentHeaderStatus": version.document.status,
        "baselineStatus": (
            version.order_engineering_baseline.status
            if version.order_engineering_baseline_id else ""
        ),
        "calculationStatus": (
            version.engineering_calculation.status
            if version.engineering_calculation_id else ""
        ),
        "bomVersionStatus": version.related_bom.status,
        "routingVersionStatus": version.related_routing.status,
        "routingVersionNo": version.related_routing.routing_version,
        "routingRevision": version.related_routing.revision,
        "routingSteps": steps,
    })


def _gate(code, label, passed, evidence, details=None):
    return {
        "code": code,
        "label": label,
        "statusCode": "PASS" if passed else "BLOCKED",
        "statusLabel": "通过" if passed else "阻断",
        "evidence": evidence,
        "details": details or {},
    }


def resolve_workflow_template():
    definitions = list(
        ProcessDefinition.objects.filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            active=True,
        ).prefetch_related("nodes").order_by("pk")
    )
    if not definitions:
        return None, None, {
            "code": "ENGINEERING_DOCUMENT_VERSION_WORKFLOW_TEMPLATE_MISSING",
            "message": "正式库缺少工程资料版本正式评审Workflow模板。",
        }
    if len(definitions) != 1:
        return None, None, {
            "code": "ENGINEERING_DOCUMENT_VERSION_WORKFLOW_TEMPLATE_AMBIGUOUS",
            "message": "正式库存在多个可适用工程资料版本Workflow模板，无法唯一解析。",
            "definitionIds": [row.pk for row in definitions],
        }
    definition = definitions[0]
    nodes = list(definition.nodes.filter(active=True).order_by("sequence", "pk"))
    if len(nodes) != 1:
        return definition, None, {
            "code": "ENGINEERING_DOCUMENT_VERSION_WORKFLOW_NODE_INVALID",
            "message": "工程资料版本最小评审模板必须且只能包含一个启用评审节点。",
            "nodeIds": [row.pk for row in nodes],
        }
    node = nodes[0]
    if node.business_action_code != REVIEW_PERMISSION:
        return definition, node, {
            "code": "ENGINEERING_DOCUMENT_VERSION_WORKFLOW_NODE_ACTION_INVALID",
            "message": "工程资料版本评审节点必须引用专用正式评审权限。",
            "permissionCode": node.business_action_code,
            "expectedPermissionCode": REVIEW_PERMISSION,
        }
    if not Permission.objects.filter(code=REVIEW_PERMISSION).exists():
        return definition, node, {
            "code": "ENGINEERING_DOCUMENT_VERSION_REVIEW_PERMISSION_MISSING",
            "message": "Workflow节点引用的工程资料版本正式评审权限不存在。",
            "permissionCode": REVIEW_PERMISSION,
        }
    return definition, node, None


def _active_workflow_responsibilities(definition, node):
    # The project supports both USE_TZ modes.  ``timezone.localdate()`` raises
    # for the naive ``timezone.now()`` produced when USE_TZ is disabled, while
    # responsibility effective dates are date-only values.
    today = date.today()
    return PositionWorkflowResponsibility.objects.select_related(
        "position", "responsibility", "workflow_node",
    ).filter(
        workflow_node=node,
        workflow_code=definition.definition_code,
        node_code=node.node_code,
        ownership_type=PositionWorkflowResponsibility.OwnershipType.REVIEWER,
        responsibility__isnull=False,
        responsibility__is_active=True,
        responsibility__status="ACTIVE",
        active=True,
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=today),
        Q(effective_to__isnull=True) | Q(effective_to__gte=today),
    ).order_by("pk")


def _maintainer_user_ids(version):
    return set(
        OrganizationOperatingAuditRecord.objects.filter(
            target_type="EngineeringDocumentVersion",
            target_id=version.pk,
            action_code="production.engineering.document.maintain",
        ).values_list("actor_id", flat=True)
    )


def eligible_review_actors(version, definition=None, node=None):
    """Resolve the complete Permission→Role→Responsibility→Position chain."""

    if definition is None or node is None:
        definition, node, template_error = resolve_workflow_template()
        if template_error:
            return []
    company_id = _company_id(version)
    role_ids = set(
        RolePermission.objects.filter(permission__code=REVIEW_PERMISSION)
        .values_list("role_id", flat=True)
    )
    if not role_ids:
        return []
    mappings = list(_active_workflow_responsibilities(definition, node))
    if not mappings:
        return []
    valid_mapping_by_position = {}
    for mapping in mappings:
        if PositionResponsibility.objects.filter(
            position_id=mapping.position_id,
            responsibility_id=mapping.responsibility_id,
            active=True,
            responsibility__is_active=True,
            responsibility__status="ACTIVE",
        ).exists():
            valid_mapping_by_position.setdefault(mapping.position_id, []).append(mapping)
    if not valid_mapping_by_position:
        return []

    assignments = UserRoleScopeAssignment.objects.filter(
        organization_id=company_id,
        role_id__in=role_ids,
        active=True,
        user__is_active=True,
        user__is_superuser=False,
    ).select_related("role", "user")
    assignments_by_user = {}
    for assignment in assignments:
        assignments_by_user.setdefault(assignment.user_id, []).append(assignment)
    employees = {
        row.user_id: row
        for row in formal_employee_queryset(
            Employee.objects.select_related(
                "position_ref", "department_ref", "user",
            ),
            company_id=company_id,
        ).filter(
            user_id__in=assignments_by_user,
            position_ref_id__in=valid_mapping_by_position,
        )
    }
    maintainers = _maintainer_user_ids(version)
    rows = []
    for user in User.objects.filter(pk__in=employees).order_by("pk"):
        employee = employees[user.pk]
        mapping = valid_mapping_by_position[employee.position_ref_id][0]
        decision = AuthorizationService.decide(
            user=user,
            action_code=REVIEW_PERMISSION,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "entity": "engineering-document-versions",
                "id": version.pk,
            },
            context={"moduleCode": "PDE", "businessWrite": True},
        )
        if not decision.get("allowed") or user.pk in maintainers:
            continue
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "departmentId": employee.department_ref_id,
            "departmentCode": employee.department_ref.code,
            "departmentName": employee.department_ref.name,
            "positionId": employee.position_ref_id,
            "positionCode": employee.position_ref.code,
            "positionName": employee.position_ref.name,
            "matchedRoleCodes": sorted(
                assignment.role.code for assignment in assignments_by_user[user.pk]
            ),
            "scopeCodes": decision.get("scope", {}).get("codes", []),
            "workflowResponsibilityId": mapping.pk,
            "responsibilityId": mapping.responsibility_id,
            "responsibilityCode": mapping.responsibility.code,
            "responsibilityName": mapping.responsibility.name,
            "ownershipType": mapping.ownership_type,
            "authorizationDecisionCode": decision.get("decisionCode", ""),
            "maintainerReviewerSeparated": True,
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
        ).select_related("actor", "task").only(
            *(field.attname for field in ApprovalDecision._meta.concrete_fields),
            *("task__" + field.attname for field in ApprovalTask._meta.concrete_fields),
            "actor__id", "actor__username", "actor__real_name",
        ).order_by("created_at", "pk")
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
        "projectionConsistent": (
            len(instances) <= 1
            and not (
                version.status == "reviewed"
                and projected != APPROVED_PROJECTION
            )
        ),
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
    ).order_by("-version", "-pk").first()
    completed = bool(
        version.status in {"reviewed", "released", "obsolete"}
        and workflow
        and workflow.status == WorkflowInstance.Status.APPROVED
        and decision
        and transition
    )
    return {
        "completed": completed,
        "projectionState": projection["projectionState"],
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
        "actionCode": REVIEW_ACTION,
    }


def project_source_completeness(version, user):
    gates = []
    identity_ready = bool(
        version.document_id
        and _company_id(version)
        and version.document_version
        and version.release_subject_type == "ORDER_ENGINEERED_PRODUCT"
    )
    gates.append(_gate(
        "ENGINEERING_DOCUMENT_VERSION_IDENTITY",
        "工程资料版本正式身份",
        identity_ready,
        (
            f"EngineeringDocument {version.document_id} / EngineeringDocumentVersion "
            f"{version.pk} / {version.document_version}"
            if identity_ready else "工程资料版本缺少正式主表、公司、版本号或订单工程主体身份。"
        ),
    ))
    gates.append(_gate(
        "ENGINEERING_DOCUMENT_VERSION_DRAFT_STATE",
        "当前版本待评审状态",
        version.status == "draft",
        f"当前状态为{version.status}；正式评审只允许draft → reviewed。",
    ))

    relation_valid = True
    relation_error = ""
    try:
        version.full_clean()
    except Exception as exc:  # ValidationError contents are evidence, not control flow.
        relation_valid = False
        relation_error = str(exc)
    gates.append(_gate(
        "ENGINEERING_DOCUMENT_VERSION_RELATION_CONTRACT",
        "工程资料版本关系合同",
        relation_valid,
        "模型外键及订单工程主体约束校验通过。" if relation_valid else relation_error,
    ))

    baseline_ready = bool(
        version.order_engineering_baseline_id
        and production_status(version.order_engineering_baseline) == "confirmed"
    )
    gates.append(_gate(
        "CONFIRMED_ENGINEERING_BASELINE",
        "已确认工程基线",
        baseline_ready,
        (
            f"EngineeringBaseline {version.order_engineering_baseline_id} / confirmed"
            if baseline_ready else "缺少已确认且与当前版本精确绑定的工程基线。"
        ),
    ))

    calculation_ready = bool(
        version.engineering_calculation_id
        and version.engineering_calculation.status == "completed"
    )
    gates.append(_gate(
        "COMPLETED_ENGINEERING_CALCULATION",
        "已完成工程核算",
        calculation_ready,
        (
            f"EngineeringCalculation {version.engineering_calculation_id} / completed"
            if calculation_ready else "缺少已完成且与当前版本精确绑定的工程核算。"
        ),
    ))

    bom_ready = version.related_bom.status == "released"
    gates.append(_gate(
        "RELEASED_BOM_VERSION",
        "已发布BOM版本",
        bom_ready,
        f"BOMVersion {version.related_bom_id} / {version.related_bom.status}",
    ))

    step_count = version.related_routing.steps.count()
    routing_ready = version.related_routing.status == "released" and step_count > 0
    gates.append(_gate(
        "RELEASED_ROUTING_VERSION",
        "已发布工艺路线版本",
        routing_ready,
        (
            f"RoutingVersion {version.related_routing_id} / "
            f"{version.related_routing.routing_version} / Rev{version.related_routing.revision} / "
            f"released / {step_count}道工序"
            if routing_ready else "工艺路线版本未发布或没有正式工序。"
        ),
        {"routingStepCount": step_count},
    ))

    exact_chain_ready = False
    chain_fact = {}
    chain_error = ""
    if version.order_engineering_instance_id:
        item = version.order_engineering_instance.sales_order_item
        try:
            chain = OrderEngineeringDocumentRegistrationService.resolve_chain(
                user=user,
                order_no=item.sales_order.order_no,
                line_no=item.line_no,
                baseline_id=version.order_engineering_baseline_id,
                calculation_id=version.engineering_calculation_id,
                bom_version_id=version.related_bom_id,
                routing_version_id=version.related_routing_id,
            )
            chain_fact = chain.as_dict()
            exact_chain_ready = (
                chain.instance.pk == version.order_engineering_instance_id
                and chain.baseline.pk == version.order_engineering_baseline_id
                and chain.calculation.pk == version.engineering_calculation_id
                and chain.bom_version.pk == version.related_bom_id
                and chain.routing.pk == version.related_routing.routing_id
                and chain.routing_version.pk == version.related_routing_id
            )
        except OrderEngineeringDocumentRegistrationError as exc:
            chain_error = exc.message
    gates.append(_gate(
        "EXACT_FORMAL_SOURCE_CHAIN",
        "准确正式来源链",
        exact_chain_ready,
        (
            "COMP001 → 订单行 → OEI → Baseline → Calculation → BOMVersion → "
            "RoutingVersion与当前工程资料版本精确一致。"
            if exact_chain_ready else chain_error or "当前资料版本与正式来源链不一致。"
        ),
        {"chain": chain_fact},
    ))

    manufacturing_count = ProductManufacturingOutput.objects.filter(
        engineering_document_version=version,
    ).count()
    gates.append(_gate(
        "NO_ENGINEERING_OR_MANUFACTURING_RELEASE",
        "未执行工程资料或制造发布",
        version.status == "draft" and manufacturing_count == 0,
        f"工程资料版本状态{version.status}；制造发布记录{manufacturing_count}条。",
        {"manufacturingOutputCount": manufacturing_count},
    ))
    return {
        "complete": all(row["statusCode"] == "PASS" for row in gates),
        "gates": gates,
        "routingStepCount": step_count,
        "exactChain": chain_fact,
        "manufacturingOutputCount": manufacturing_count,
    }


def project_review_preflight(version, user):
    completeness = project_source_completeness(version, user)
    permission_exists = Permission.objects.filter(code=REVIEW_PERMISSION).exists()
    definition, node, template_error = resolve_workflow_template()
    workflow_mappings = list(
        _active_workflow_responsibilities(definition, node)
        if definition and node and not template_error else []
    )
    actors = eligible_review_actors(version, definition, node) if not template_error else []
    current_actor = next((row for row in actors if row["userId"] == user.pk), None)
    readback = review_readback(version)
    no_existing_review = not readback["completed"] and not workflow_projection(version)["instances"]
    gates = list(completeness["gates"])
    gates.extend([
        _gate(
            "NO_DUPLICATE_FORMAL_REVIEW",
            "无重复正式评审决定",
            no_existing_review,
            "当前没有工程资料版本正式Workflow实例或决定。"
            if no_existing_review else "当前版本已存在正式评审实例或决定，不得重复提交。",
        ),
        _gate(
            "REVIEW_PERMISSION_REGISTERED",
            "专用正式评审权限",
            permission_exists,
            f"已存在 {REVIEW_PERMISSION}。"
            if permission_exists else f"正式库尚未登记 {REVIEW_PERMISSION}。",
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
            "WORKFLOW_RESPONSIBILITY_READY",
            "岗位流程评审责任",
            bool(workflow_mappings),
            (
                f"已配置{len(workflow_mappings)}条启用的REVIEWER岗位流程责任。"
                if workflow_mappings else "尚未任命该Workflow节点的正式REVIEWER岗位责任。"
            ),
        ),
        _gate(
            "AUTHORIZED_REVIEWER_AVAILABLE",
            "合法正式评审人员",
            bool(actors),
            (
                f"已解析{len(actors)}名同时满足专用权限、角色、COMP001 Scope、"
                "员工、岗位、岗位职责及流程责任的非管理员评审人。"
                if actors else "未解析到完整合法的工程资料版本正式评审责任链。"
            ),
        ),
    ])
    first_blocker = next((row for row in gates if row["statusCode"] != "PASS"), None)
    ready_for_human_review = bool(
        version.status == "draft"
        and not first_blocker
        and not readback["completed"]
    )
    return {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": REVIEW_ACTION,
        "permissionCode": REVIEW_PERMISSION,
        "targetStatusCode": "reviewed",
        "targetStatusLabel": "已评审",
        "readyForHumanReview": ready_for_human_review,
        "reviewAllowed": ready_for_human_review and bool(current_actor),
        "currentBrowserOperable": ready_for_human_review and bool(current_actor),
        "humanReviewerAuthorizationRequired": (
            permission_exists and not template_error and not actors
        ),
        "decisionCode": (
            "PASS_READY_FOR_HUMAN_REVIEW" if ready_for_human_review else
            "PASS_FORMAL_REVIEW_COMPLETE" if readback["completed"] else
            "BLOCKED"
        ),
        "decisionLabel": (
            "具备人工正式评审条件" if ready_for_human_review else
            "正式评审已完成" if readback["completed"] else
            "暂不具备人工正式评审条件"
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
            "workflowResponsibilityCount": len(workflow_mappings),
            "blocker": template_error or {},
        },
        "eligibleReviewActors": actors,
        "currentActor": current_actor or {},
        "currentUser": {
            "userId": user.pk,
            "username": user.username,
            "realName": user.real_name,
            "isSuperuser": user.is_superuser,
        },
        "completeness": completeness,
        "reviewReadback": readback,
        "databaseBusinessWriteCount": 0,
    }


def _require_actor(version, user, definition, node):
    actor = next(
        (
            row for row in eligible_review_actors(version, definition, node)
            if row["userId"] == user.pk
        ),
        None,
    )
    if not actor:
        raise EngineeringDocumentVersionReviewError(
            "PERMISSION_DENIED",
            "当前登录人员不具备工程资料版本正式评审的完整责任链。",
            403,
            {"permissionCode": REVIEW_PERMISSION},
        )
    return actor


def _reserve_request(*, version, user, reason, key):
    key = str(key or "").strip()
    if not key:
        raise EngineeringDocumentVersionReviewError(
            "IDEMPOTENCY_KEY_REQUIRED", "正式评审必须提供Idempotency-Key。", 409,
        )
    payload = {
        "contractVersion": CONTROL_CONTRACT,
        "actionCode": REVIEW_ACTION,
        "engineeringDocumentVersionId": version.pk,
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
            raise EngineeringDocumentVersionReviewError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同工程资料版本评审payload。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise EngineeringDocumentVersionReviewError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity已有未完成的工程资料版本评审。",
            409,
        )
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=_company_id(version),
        source_system="PCE_ENGINEERING_DOCUMENT_VERSION_REVIEW",
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
        raise EngineeringDocumentVersionReviewError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "现有ExternalIdentity与当前工程资料版本范围不一致。",
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


@transaction.atomic
def review_engineering_document_version(*, object_id, user, reason, idempotency_key, action=""):
    reason = str(reason or "").strip()
    if not reason:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_REASON_REQUIRED",
            "正式评审意见必须填写。",
            422,
        )
    if action and str(action).strip() != REVIEW_ACTION:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_ACTION_CONFLICT",
            "请求action与工程资料版本正式评审动作不一致。",
            409,
        )
    version = EngineeringDocumentVersion.objects.select_for_update().select_related(
        "document", "related_product", "order_engineering_instance__company",
        "order_engineering_instance__sales_order_item__sales_order",
        "order_engineering_baseline", "engineering_calculation",
        "related_bom__bom", "related_routing__routing",
    ).filter(pk=object_id).first()
    if not version:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_NOT_FOUND", "待评审工程资料版本不存在。", 404,
        )
    if _company_id(version) != user.company_id:
        raise EngineeringDocumentVersionReviewError(
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
    if version.status != "draft":
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_STATE_CONFLICT",
            f"正式评审要求当前状态为draft，实际为{version.status}。",
            409,
        )
    definition, node, template_error = resolve_workflow_template()
    if template_error:
        raise EngineeringDocumentVersionReviewError(
            template_error["code"], template_error["message"], 422, template_error,
        )
    authorization = _require_actor(version, user, definition, node)
    completeness = project_source_completeness(version, user)
    failed = [row for row in completeness["gates"] if row["statusCode"] != "PASS"]
    if failed:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_GATE_BLOCKED",
            "工程资料版本评审完整性Gate未全部通过。",
            422,
            {"failedGates": failed},
        )
    existing = list(
        WorkflowInstance.objects.select_for_update().filter(
            document_type__in=WORKFLOW_DOCUMENT_TYPES,
            document_id=version.pk,
        )
    )
    if existing:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_WORKFLOW_ALREADY_EXISTS",
            "该工程资料版本已有正式Workflow实例，不得重复形成评审决定。",
            409,
        )
    matched_roles = authorization.get("matchedRoleCodes") or []
    if not matched_roles:
        raise EngineeringDocumentVersionReviewError(
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_ROLE_REQUIRED",
            "当前评审人员没有与Workflow节点权限匹配的正式角色。",
            403,
        )

    content_snapshot = _content_snapshot(version)
    content_hash = _hash(content_snapshot)
    workflow = WorkflowInstance.objects.create(
        instance_no=f"WFI-EDV-{version.pk}-{request.pk}",
        process_definition=definition,
        document_type=DOCUMENT_TYPE,
        document_id=version.pk,
        status=WorkflowInstance.Status.PENDING,
        current_step=1,
        total_steps=1,
    )
    task = ApprovalTask.objects.create(
        task_no=f"APT-EDV-{version.pk}-{request.pk}-01",
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
            "contentHash": content_hash,
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
        target_label=f"{version.document.document_no} / {version.document_version}",
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
            "reviewContentSnapshot": content_snapshot,
            "reviewContentHash": content_hash,
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
    result = {
        "contractVersion": CONTROL_CONTRACT,
        "idempotentReplay": False,
        "engineeringDocumentVersion": _snapshot(version),
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
        "reviewContentHash": content_hash,
        "requestIdentity": request.idempotency_key,
        "writeRequestId": request.pk,
        "engineeringDocumentReleaseExecuted": False,
        "manufacturingReleaseExecuted": False,
    }
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(version.pk)
    request.result = result
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return result


__all__ = [
    "APPROVED_PROJECTION",
    "CONTROL_CONTRACT",
    "REVIEW_ACTION",
    "REVIEW_PERMISSION",
    "EngineeringDocumentVersionReviewError",
    "eligible_review_actors",
    "project_review_preflight",
    "project_source_completeness",
    "review_engineering_document_version",
    "review_readback",
]
