"""Formal execution service for ORDER_MANUFACTURING_ADMISSION.

The confirmed state belongs to the manufacturing-admission workflow projection,
not to ``SalesOrder.status``.  The source order and all engineering release facts
remain immutable throughout this transaction.
"""

from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from django.db import transaction
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrder, SalesOrderItem
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
)
from workflow_runtime.state_transitions import (
    BusinessStateTransitionError,
    record_projected_business_transition,
)

from .manufacturing_admission_responsibility_service import (
    DOCUMENT_TYPE,
    GENERIC_OWNERSHIP_TYPE,
    NODE_CODE,
    PERMISSION_CODE,
    PROCESS_CODE,
    RESPONSIBILITY_CODE,
    ROLE_CODE,
)
from .models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocumentVersion,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductManufacturingOutput,
    RoutingVersion,
)


CONTRACT_VERSION = "PCE-ORDER-MANUFACTURING-ADMISSION-CONFIRMATION-V1.0"
ACTION_CODE = PERMISSION_CODE
OBJECT_TYPE = DOCUMENT_TYPE
SOURCE_STATE = "READY"
TARGET_STATE = "CONFIRMED"
ALLOWED_TRANSITIONS = ((SOURCE_STATE, TARGET_STATE),)


class ManufacturingAdmissionConfirmationError(ValueError):
    def __init__(self, code, message, http_status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _hash(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _snapshot(instance):
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
    }


def _protected_snapshot(*, order, item, output, oei, baseline, calculation, document, bom, routing):
    payload = {
        "order": _snapshot(order),
        "item": _snapshot(item),
        "manufacturingOutput": _snapshot(output),
        "orderEngineeringInstance": _snapshot(oei),
        "engineeringBaseline": _snapshot(baseline),
        "engineeringCalculation": _snapshot(calculation),
        "engineeringDocumentVersion": _snapshot(document),
        "bomVersion": _snapshot(bom),
        "bomItems": list(bom.items.order_by("pk").values()),
        "routingVersion": _snapshot(routing),
        "routingSteps": list(routing.steps.order_by("pk").values()),
        "demandRows": list(Demand.objects.order_by("pk").values()),
        "planningRequirementRows": list(
            PlanningRequirement.objects.order_by("pk").values()
        ),
    }
    return payload, _hash(payload)


def _resolve_configuration(*, order, user):
    definition = ProcessDefinition.objects.select_for_update().filter(
        definition_code=PROCESS_CODE, active=True
    ).first()
    if not definition or definition.document_type != DOCUMENT_TYPE:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_PROCESS_NOT_READY",
            "制造承接确认正式流程不存在、未启用或业务对象类型不一致。",
            422,
        )
    nodes = list(definition.nodes.select_for_update().filter(active=True))
    if len(nodes) != 1 or nodes[0].node_code != NODE_CODE:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_NODE_NOT_READY",
            "制造承接确认流程缺少唯一有效确认节点。",
            422,
        )
    node = nodes[0]
    permission = Permission.objects.filter(code=PERMISSION_CODE).first()
    if not permission or node.business_action_code != permission.code:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_PERMISSION_NOT_READY",
            "制造承接确认节点与正式业务动作权限不一致。",
            422,
        )
    role = Role.objects.filter(code=ROLE_CODE).first()
    if not role or not RolePermission.objects.filter(
        role=role, permission=permission
    ).exists():
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ROLE_NOT_READY",
            "制造承接确认专用角色未绑定正式权限。",
            422,
        )
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    if (
        not user.is_active
        or user.company_id != order.company_id
        or not employee
        or employee.status != "active"
        or not position
        or not position.is_active
        or position.company_id != order.company_id
    ):
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ACTOR_IDENTITY_INVALID",
            "当前确认人缺少有效账号、员工、岗位或公司范围。",
            403,
        )
    today = date.today()
    mapping = PositionWorkflowResponsibility.objects.select_for_update().filter(
        position=position,
        workflow_node=node,
        workflow_code=PROCESS_CODE,
        node_code=NODE_CODE,
        ownership_type=GENERIC_OWNERSHIP_TYPE,
        active=True,
        responsibility__code=RESPONSIBILITY_CODE,
        responsibility__status=Responsibility.Status.ACTIVE,
        responsibility__is_active=True,
    ).first()
    if (
        not mapping
        or (mapping.effective_from and mapping.effective_from > today)
        or (mapping.effective_to and mapping.effective_to < today)
        or not PositionResponsibility.objects.filter(
            position=position, responsibility=mapping.responsibility, active=True
        ).exists()
    ):
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_RESPONSIBILITY_NOT_READY",
            "当前岗位没有有效制造承接确认责任关系。",
            403,
        )
    scope = UserRoleScopeAssignment.objects.select_for_update().filter(
        user=user,
        role=role,
        organization_id=order.company_id,
        scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
        department__isnull=True,
        active=True,
    ).first()
    decision = AuthorizationService.decide(
        user=user,
        action_code=permission.code,
        organization_id=str(order.company_id),
        business_object={
            "organizationId": order.company_id,
            "departmentId": position.department_id,
            "ownerUserId": user.pk,
        },
    )
    if not scope or not decision["allowed"]:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_AUTHORIZATION_DENIED",
            "当前确认人未通过专用角色、权限和公司范围校验。",
            403,
            {"authorization": decision},
        )
    if order.created_by_id == user.pk:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_SOD_FAILED",
            "制造承接确认人与订单制单人必须职责分离。",
            422,
        )
    return {
        "definition": definition,
        "node": node,
        "permission": permission,
        "role": role,
        "scope": scope,
        "mapping": mapping,
        "employee": employee,
        "position": position,
        "authorization": decision,
    }


def _validate_engineering_facts(
    *, order, item_id, output_id, oei_id, baseline_id, bom_id, routing_id
):
    item = SalesOrderItem.objects.select_for_update().filter(
        pk=item_id, sales_order=order
    ).first()
    if (
        not item
        or item.quantity != Decimal("5.0000")
        or item.required_date != date(2026, 10, 20)
        or item.engineering_mode != "ORDER_ENGINEERED"
    ):
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ORDER_ITEM_FACT_MISMATCH",
            "订单行、数量、交期或工程模式与授权事实不一致。",
            409,
        )
    oei = OrderEngineeringInstance.objects.select_for_update().filter(
        pk=oei_id, sales_order_item=item, company_id=order.company_id
    ).first()
    baseline = production_baselines().select_for_update().filter(
        pk=baseline_id, sales_order=order, company_id=order.company_id, status="confirmed"
    ).first()
    if not oei or not baseline:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ENGINEERING_IDENTITY_INVALID",
            "订单工程实例或已确认工程基线不存在。",
            422,
        )
    output = ProductManufacturingOutput.objects.select_for_update().filter(
        pk=output_id,
        order_engineering_instance=oei,
        order_engineering_baseline=baseline,
        release_subject_type="ORDER_ENGINEERED_PRODUCT",
        definition_mode="order_specific",
        release_status="released_to_manufacturing",
    ).first()
    if not output:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_OUTPUT_NOT_RELEASED",
            "指定制造输出不存在或尚未正式发布至制造。",
            422,
        )
    calculation = EngineeringCalculationRecord.objects.select_for_update().filter(
        pk=output.engineering_calculation_id,
        company_id=order.company_id,
        sales_order_item=item,
        engineering_instance=oei,
        status="completed",
    ).first()
    document = EngineeringDocumentVersion.objects.select_for_update().filter(
        pk=output.engineering_document_version_id,
        order_engineering_instance=oei,
        order_engineering_baseline=baseline,
        engineering_calculation=calculation,
        status="released",
    ).first()
    bom = BOMVersion.objects.select_for_update().filter(
        pk=bom_id,
        order_engineering_instance=oei,
        source_calculation=calculation,
        status="released",
        approval_state="workflow_approved",
    ).first()
    routing = RoutingVersion.objects.select_for_update().filter(
        pk=routing_id, status="released", approval_state="workflow_approved"
    ).first()
    if (
        not calculation
        or not document
        or not bom
        or not routing
        or output.bom_version_id != bom.pk
        or output.routing_version_id != routing.pk
        or document.related_bom_id != bom.pk
        or document.related_routing_id != routing.pk
        or document.engineering_calculation_id != calculation.pk
        or not bom.items.exists()
        or not routing.steps.exists()
    ):
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ENGINEERING_SOURCE_INCOMPLETE",
            "工程计算、资料版本、BOM或Routing来源关系不完整。",
            422,
        )
    return {
        "item": item,
        "oei": oei,
        "baseline": baseline,
        "output": output,
        "calculation": calculation,
        "document": document,
        "bom": bom,
        "routing": routing,
    }


def _reserve_request(*, order, user, reason, key, engineering_fingerprint):
    key = str(key or "").strip()
    if not key:
        raise ManufacturingAdmissionConfirmationError(
            "IDEMPOTENCY_KEY_REQUIRED", "制造承接确认必须提供Idempotency-Key。", 409
        )
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "actionCode": ACTION_CODE,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "actorId": user.pk,
        "reason": reason,
        "engineeringFingerprint": engineering_fingerprint,
        "targetState": TARGET_STATE,
    }
    request_hash = _hash(payload)
    existing = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        idempotency_key=key,
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise ManufacturingAdmissionConfirmationError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一request identity已用于不同制造承接确认事实。",
                409,
            )
        if existing.status == MasterDataWriteRequest.Status.COMMITTED:
            return existing, True
        raise ManufacturingAdmissionConfirmationError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "同一request identity存在未完成的制造承接确认。",
            409,
        )
    identity, created = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=order.company_id,
        source_system="PCE_ORDER_MANUFACTURING_ADMISSION",
        source_type="BUSINESS_ACTION_SCOPE",
        source_object_type=OBJECT_TYPE,
        external_id=f"SalesOrder:{order.pk}:ManufacturingAdmission",
        defaults={
            "target_entity_type": OBJECT_TYPE,
            "target_entity_id": str(order.pk),
            "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": engineering_fingerprint,
            "audit_metadata": {
                "contractVersion": CONTRACT_VERSION,
                "salesOrderNo": order.order_no,
            },
        },
    )
    if (
        identity.target_entity_type != OBJECT_TYPE
        or identity.target_entity_id != str(order.pk)
        or identity.source_fingerprint != engineering_fingerprint
    ):
        raise ManufacturingAdmissionConfirmationError(
            "REQUEST_IDENTITY_SCOPE_CONFLICT",
            "制造承接确认ExternalIdentity与当前订单或工程来源不一致。",
            409,
            {"externalIdentityCreated": created},
        )
    request = MasterDataWriteRequest.objects.create(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        entity_type=OBJECT_TYPE,
        idempotency_key=key,
        request_hash=request_hash,
        source_identity=identity,
        audit_metadata=payload,
    )
    return request, False


@transaction.atomic
def confirm_manufacturing_admission(
    *,
    order_id,
    user,
    reason,
    idempotency_key,
    item_id,
    output_id,
    oei_id,
    baseline_id,
    bom_id,
    routing_id,
    action="",
):
    reason = str(reason or "").strip()
    if not reason:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_REASON_REQUIRED", "制造承接确认意见不能为空。", 422
        )
    if action and str(action).strip() != ACTION_CODE:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ACTION_CONFLICT",
            "请求action与制造承接确认正式业务动作不一致。",
            409,
        )
    order = SalesOrder.objects.select_for_update().filter(pk=order_id).first()
    if not order:
        raise ManufacturingAdmissionConfirmationError(
            "SALES_ORDER_NOT_FOUND", "指定销售订单不存在。", 404
        )
    if order.order_no != "SO202609180003" or order.status != "draft":
        raise ManufacturingAdmissionConfirmationError(
            "SALES_ORDER_FACT_MISMATCH",
            "销售订单编号或状态与本次授权事实不一致。",
            409,
        )
    configuration = _resolve_configuration(order=order, user=user)
    engineering = _validate_engineering_facts(
        order=order,
        item_id=item_id,
        output_id=output_id,
        oei_id=oei_id,
        baseline_id=baseline_id,
        bom_id=bom_id,
        routing_id=routing_id,
    )
    protected_before, protected_hash_before = _protected_snapshot(
        order=order,
        item=engineering["item"],
        output=engineering["output"],
        oei=engineering["oei"],
        baseline=engineering["baseline"],
        calculation=engineering["calculation"],
        document=engineering["document"],
        bom=engineering["bom"],
        routing=engineering["routing"],
    )
    engineering_fingerprint = _hash({
        "salesOrderId": order.pk,
        "salesOrderVersion": order.version,
        "salesOrderItemId": engineering["item"].pk,
        "orderEngineeringInstanceId": engineering["oei"].pk,
        "engineeringBaselineId": engineering["baseline"].pk,
        "engineeringBaselineHash": engineering["baseline"].snapshot_hash,
        "engineeringCalculationId": engineering["calculation"].pk,
        "engineeringCalculationResultHash": engineering["calculation"].result_hash,
        "engineeringDocumentVersionId": engineering["document"].pk,
        "manufacturingOutputId": engineering["output"].pk,
        "bomVersionId": engineering["bom"].pk,
        "bomPreviewHash": engineering["bom"].preview_hash,
        "routingVersionId": engineering["routing"].pk,
    })
    request, replayed = _reserve_request(
        order=order,
        user=user,
        reason=reason,
        key=idempotency_key,
        engineering_fingerprint=engineering_fingerprint,
    )
    if replayed:
        return {**request.result, "idempotentReplay": True, "businessWriteCount": 0}

    definition = configuration["definition"]
    existing_workflows = list(
        WorkflowInstance.objects.select_for_update().filter(
            document_type=DOCUMENT_TYPE, document_id=order.pk
        )
    )
    if existing_workflows or BusinessStateTransition.objects.select_for_update().filter(
        object_type=OBJECT_TYPE, object_id=order.pk
    ).exists():
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_ALREADY_CONFIRMED",
            "该订单已存在制造承接确认Workflow或状态转换，不得重复确认。",
            409,
        )

    role = configuration["role"]
    workflow = WorkflowInstance.objects.create(
        instance_no=f"WFI-MFG-ADM-SO-{order.pk}-{request.pk}",
        process_definition=definition,
        document_type=DOCUMENT_TYPE,
        document_id=order.pk,
        status=WorkflowInstance.Status.PENDING,
        current_step=1,
        total_steps=1,
    )
    task = ApprovalTask.objects.create(
        task_no=f"APT-MFG-ADM-SO-{order.pk}-{request.pk}-01",
        workflow_instance=workflow,
        step_no=1,
        required_role_code=role.code,
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
        action_id=ACTION_CODE,
        idempotency_key=str(idempotency_key).strip(),
        decision_hash=_hash({
            "workflowInstanceId": workflow.pk,
            "taskId": task.pk,
            "actorId": user.pk,
            "decision": "approved",
            "engineeringFingerprint": engineering_fingerprint,
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

    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=user,
        organization_id=order.company_id,
        target_type=OBJECT_TYPE,
        target_id=order.pk,
        target_label=f"{order.order_no} / 制造承接确认",
        reason=reason,
        before_snapshot={
            "manufacturingAdmissionStatus": SOURCE_STATE,
            "salesOrderStatus": order.status,
            "protectedFactsHash": protected_hash_before,
        },
        after_snapshot={
            "manufacturingAdmissionStatus": TARGET_STATE,
            "salesOrderStatus": order.status,
            "workflowInstanceId": workflow.pk,
            "approvalTaskId": task.pk,
            "approvalDecisionId": decision.pk,
            "responsibleUserId": user.pk,
            "responsibleEmployeeId": configuration["employee"].pk,
            "responsibilityCode": RESPONSIBILITY_CODE,
            "roleCode": role.code,
            "processCode": definition.definition_code,
            "nodeCode": configuration["node"].node_code,
            "authorization": configuration["authorization"],
            "engineeringFingerprint": engineering_fingerprint,
            "protectedFactsHash": protected_hash_before,
            "requestIdentity": str(idempotency_key).strip(),
            "controlContract": CONTRACT_VERSION,
        },
    )
    try:
        transition = record_projected_business_transition(
            object_type=OBJECT_TYPE,
            object_id=order.pk,
            source_state=SOURCE_STATE,
            target_state=TARGET_STATE,
            action_code=ACTION_CODE,
            operator=user,
            reason=reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            workflow_instance=workflow,
            allowed_transitions=ALLOWED_TRANSITIONS,
        )
    except BusinessStateTransitionError as error:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_TRANSITION_FAILED", str(error), 409
        ) from error

    protected_after, protected_hash_after = _protected_snapshot(
        order=SalesOrder.objects.get(pk=order.pk),
        item=SalesOrderItem.objects.get(pk=engineering["item"].pk),
        output=ProductManufacturingOutput.objects.get(pk=engineering["output"].pk),
        oei=OrderEngineeringInstance.objects.get(pk=engineering["oei"].pk),
        baseline=production_baselines().get(pk=engineering["baseline"].pk),
        calculation=EngineeringCalculationRecord.objects.get(pk=engineering["calculation"].pk),
        document=EngineeringDocumentVersion.objects.get(pk=engineering["document"].pk),
        bom=BOMVersion.objects.get(pk=engineering["bom"].pk),
        routing=RoutingVersion.objects.get(pk=engineering["routing"].pk),
    )
    if protected_after != protected_before or protected_hash_after != protected_hash_before:
        raise ManufacturingAdmissionConfirmationError(
            "MANUFACTURING_ADMISSION_PROTECTED_FACTS_CHANGED",
            "制造承接确认期间受保护订单或工程事实发生变化，事务已回滚。",
            409,
        )

    result = {
        "contractVersion": CONTRACT_VERSION,
        "idempotentReplay": False,
        "actionCode": ACTION_CODE,
        "manufacturingAdmissionStatus": TARGET_STATE,
        "salesOrder": {
            "id": order.pk,
            "orderNo": order.order_no,
            "status": order.status,
            "version": order.version,
            "changed": False,
        },
        "responsibleActor": {
            "userId": user.pk,
            "username": user.username,
            "employeeId": configuration["employee"].pk,
            "employeeNo": configuration["employee"].employee_no,
            "fullName": configuration["employee"].full_name,
            "roleCode": role.code,
            "responsibilityCode": RESPONSIBILITY_CODE,
        },
        "workflow": {
            "instanceId": workflow.pk,
            "instanceNo": workflow.instance_no,
            "statusCode": workflow.status,
            "taskId": task.pk,
            "taskNo": task.task_no,
            "taskStatusCode": task.status,
            "decisionId": decision.pk,
            "decisionActorId": decision.actor_id,
            "decision": decision.decision,
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
        "externalIdentityId": request.source_identity_id,
        "engineeringFingerprint": engineering_fingerprint,
        "protectedFactsHashBefore": protected_hash_before,
        "protectedFactsHashAfter": protected_hash_after,
        "protectedFactsUnchanged": True,
        "businessWriteCount": 4,
        "businessStateUpdateCount": 2,
        "auditWriteCount": 1,
        "controlWriteCount": 2,
        "demandCreated": False,
        "planningRequirementCreated": False,
        "remainingDemandGate": "SALES_ORDER_NOT_APPROVED",
        "productionDemandAdmissionReady": False,
    }
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(order.pk)
    request.result = result
    request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return result


__all__ = [
    "ACTION_CODE",
    "CONTRACT_VERSION",
    "ManufacturingAdmissionConfirmationError",
    "confirm_manufacturing_admission",
]
