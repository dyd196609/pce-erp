"""Read-only verification for SO202609180003 manufacturing admission confirmation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_DATABASE_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
PROCESS_CODE = "ORDER_MANUFACTURING_ADMISSION"
DOCUMENT_TYPE = "SalesOrderManufacturingAdmission"
ACTION_CODE = "pde.order.manufacturing_admission.confirm"
ROLE_CODE = "manufacturing_admission_approver"
RESPONSIBILITY_CODE = "MANUFACTURING_ADMISSION_APPROVER"
REQUEST_IDENTITY = "SO202609180003-MANUFACTURING-ADMISSION-CONFIRM-V1"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


configured_database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if configured_database != EXPECTED_DATABASE:
    raise RuntimeError(f"PCE_DATABASE_PATH must be {EXPECTED_DATABASE}")
if os.environ.get("PCE_DATABASE_IDENTITY") != EXPECTED_DATABASE_IDENTITY:
    raise RuntimeError(f"PCE_DATABASE_IDENTITY must be {EXPECTED_DATABASE_IDENTITY}")
if os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") != "1":
    raise RuntimeError("PCE_NON_PRODUCTION_ACCEPTANCE must be 1")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrder, SalesOrderItem
from sales.services import SalesBusinessError, generate_demand
from system.authorization import AuthorizationService
from system.models import (
    OrganizationOperatingAuditRecord,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
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
from pde.models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocumentVersion,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductManufacturingOutput,
    RoutingVersion,
)
from django.db import connection


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


hash_before = file_hash(EXPECTED_DATABASE)
demand_count_before = Demand.objects.count()
planning_count_before = PlanningRequirement.objects.count()

order = SalesOrder.objects.get(pk=3)
item = SalesOrderItem.objects.get(pk=3)
output = ProductManufacturingOutput.objects.get(pk=1)
oei = OrderEngineeringInstance.objects.get(pk=2)
baseline = OrderEngineeringBaseline.objects.get(pk=2)
calculation = EngineeringCalculationRecord.objects.get(pk=3)
document = EngineeringDocumentVersion.objects.get(pk=1)
bom = BOMVersion.objects.get(pk=3)
routing = RoutingVersion.objects.get(pk=43)
actor = User.objects.get(pk=30)
employee = actor.employee_profile
position = employee.position_ref
creator = User.objects.get(pk=11)

require(order.order_no == "SO202609180003", "ORDER_NO_MISMATCH")
require(order.status == "draft" and order.version == 2, "ORDER_STATE_CHANGED")
require(order.created_by_id == 11, "ORDER_CREATOR_CHANGED")
require(item.sales_order_id == 3, "ORDER_ITEM_RELATION_CHANGED")
require(str(item.quantity) == "5.0000", "ORDER_ITEM_QUANTITY_CHANGED")
require(item.required_date.isoformat() == "2026-10-20", "ORDER_ITEM_DATE_CHANGED")
require(item.engineering_mode == "ORDER_ENGINEERED", "ORDER_ITEM_MODE_CHANGED")
require(oei.sales_order_item_id == 3 and oei.company_id == 1, "OEI_RELATION_CHANGED")
require(baseline.sales_order_id == 3 and baseline.status == "confirmed", "BASELINE_CHANGED")
require(calculation.sales_order_item_id == 3 and calculation.status == "completed", "CALCULATION_CHANGED")
require(
    output.order_engineering_instance_id == 2
    and output.order_engineering_baseline_id == 2
    and output.engineering_calculation_id == 3
    and output.engineering_document_version_id == 1
    and output.bom_version_id == 3
    and output.routing_version_id == 43
    and output.release_status == "released_to_manufacturing",
    "MANUFACTURING_OUTPUT_CHANGED",
)
require(
    document.order_engineering_instance_id == 2
    and document.order_engineering_baseline_id == 2
    and document.engineering_calculation_id == 3
    and document.related_bom_id == 3
    and document.related_routing_id == 43
    and document.status == "released",
    "ENGINEERING_DOCUMENT_SOURCE_CHANGED",
)
require(bom.status == "released" and bom.approval_state == "workflow_approved", "BOM_CHANGED")
require(bom.items.exists(), "BOM_ITEMS_MISSING")
require(routing.status == "released" and routing.approval_state == "workflow_approved", "ROUTING_CHANGED")
require(routing.steps.exists(), "ROUTING_STEPS_MISSING")

definition = ProcessDefinition.objects.get(definition_code=PROCESS_CODE)
require(definition.active and definition.document_type == DOCUMENT_TYPE, "PROCESS_NOT_ACTIVE")
node = definition.nodes.get(node_code="MANUFACTURING_ADMISSION_CONFIRM", active=True)
require(node.business_action_code == ACTION_CODE, "PROCESS_ACTION_MISMATCH")
role = Role.objects.get(code=ROLE_CODE)
responsibility = Responsibility.objects.get(code=RESPONSIBILITY_CODE)
require(
    actor.is_active
    and actor.username == "pce_emp_comp001_0001"
    and actor.company_id == 1
    and employee.pk == 122
    and employee.employee_no == "EMP-COMP001-0001"
    and employee.full_name == "赵铁柱"
    and employee.status == "active"
    and position.is_active
    and actor.pk != creator.pk,
    "RESPONSIBLE_ACTOR_FACT_MISMATCH",
)
require(RolePermission.objects.filter(role=role, permission__code=ACTION_CODE).exists(), "ROLE_PERMISSION_MISSING")
require(
    UserRoleScopeAssignment.objects.filter(
        user=actor,
        role=role,
        organization_id=1,
        scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
        active=True,
    ).exists(),
    "ROLE_SCOPE_MISSING",
)
require(
    PositionResponsibility.objects.filter(
        position=position, responsibility=responsibility, active=True
    ).exists(),
    "POSITION_RESPONSIBILITY_MISSING",
)
require(
    PositionWorkflowResponsibility.objects.filter(
        position=position,
        responsibility=responsibility,
        workflow_node=node,
        workflow_code=PROCESS_CODE,
        node_code=node.node_code,
        active=True,
    ).exists(),
    "WORKFLOW_RESPONSIBILITY_MISSING",
)
authorization = AuthorizationService.decide(
    user=actor,
    action_code=ACTION_CODE,
    organization_id="1",
    business_object={
        "organizationId": 1,
        "departmentId": position.department_id,
        "ownerUserId": actor.pk,
    },
)
require(authorization["allowed"], "AUTHORIZATION_DENIED")

workflow = WorkflowInstance.objects.get(document_type=DOCUMENT_TYPE, document_id=3)
require(workflow.process_definition_id == definition.pk and workflow.status == "approved", "WORKFLOW_NOT_APPROVED")
task = ApprovalTask.objects.get(workflow_instance=workflow)
require(task.status == "approved" and task.required_role_code == ROLE_CODE, "APPROVAL_TASK_NOT_APPROVED")
decision = ApprovalDecision.objects.get(task=task)
require(
    decision.actor_id == 30
    and decision.decision == "approved"
    and decision.action_id == ACTION_CODE
    and decision.idempotency_key == REQUEST_IDENTITY,
    "APPROVAL_DECISION_MISMATCH",
)
transition = BusinessStateTransition.objects.get(object_type=DOCUMENT_TYPE, object_id=3)
require(
    transition.source_state == "READY"
    and transition.target_state == "CONFIRMED"
    and transition.action_code == ACTION_CODE
    and transition.operator_id == 30
    and transition.workflow_instance_id == workflow.pk,
    "BUSINESS_TRANSITION_MISMATCH",
)
audit = OrganizationOperatingAuditRecord.objects.get(
    action_code=ACTION_CODE,
    target_type=DOCUMENT_TYPE,
    target_id=3,
)
require(
    audit.actor_id == 30
    and audit.after_snapshot.get("workflowInstanceId") == workflow.pk
    and audit.after_snapshot.get("approvalDecisionId") == decision.pk
    and audit.after_snapshot.get("manufacturingAdmissionStatus") == "CONFIRMED"
    and audit.after_snapshot.get("salesOrderStatus") == "draft",
    "AUDIT_FACT_MISMATCH",
)
require(transition.audit_reference == f"OrganizationOperatingAuditRecord:{audit.pk}", "AUDIT_LINK_MISMATCH")
write_request = MasterDataWriteRequest.objects.get(
    organization_id=1,
    action_code=ACTION_CODE,
    idempotency_key=REQUEST_IDENTITY,
)
identity = ExternalIdentity.objects.get(pk=write_request.source_identity_id)
require(write_request.status == "COMMITTED" and write_request.target_entity_id == "3", "WRITE_REQUEST_NOT_COMMITTED")
require(
    identity.target_entity_type == DOCUMENT_TYPE
    and identity.target_entity_id == "3"
    and identity.mapping_status == "MATCH",
    "EXTERNAL_IDENTITY_MISMATCH",
)

# Execute the existing server-side demand gate with the order's sales coordinator.
# The draft-state rejection occurs before any demand write.
demand_gate = None
try:
    generate_demand(
        user=creator,
        order_id=3,
        authorization={"verification": "read-only"},
    )
except SalesBusinessError as error:
    demand_gate = error.code
require(demand_gate == "SALES_ORDER_NOT_APPROVED", "DEMAND_GATE_NOT_PRESERVED")

demand_count_after = Demand.objects.count()
planning_count_after = PlanningRequirement.objects.count()
require(demand_count_after == demand_count_before, "DEMAND_COUNT_CHANGED")
require(planning_count_after == planning_count_before, "PLANNING_REQUIREMENT_COUNT_CHANGED")

connection.close()
hash_after = file_hash(EXPECTED_DATABASE)
require(hash_after == hash_before, "READ_ONLY_VERIFICATION_CHANGED_DATABASE")

result = {
    "result": "PASS",
    "contractVersion": "PCE-ORDER-MANUFACTURING-ADMISSION-CONFIRMATION-V1.0",
    "database": {
        "path": str(EXPECTED_DATABASE),
        "sha256Before": hash_before,
        "sha256After": hash_after,
        "unchangedDuringVerification": True,
    },
    "responsibleActor": {
        "userId": actor.pk,
        "username": actor.username,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "roleCode": role.code,
        "responsibilityCode": responsibility.code,
        "authorizationAllowed": authorization["allowed"],
    },
    "workflow": {
        "processDefinitionId": definition.pk,
        "instanceId": workflow.pk,
        "instanceNo": workflow.instance_no,
        "status": workflow.status,
        "taskId": task.pk,
        "taskNo": task.task_no,
        "taskStatus": task.status,
        "decisionId": decision.pk,
        "decisionActorId": decision.actor_id,
        "decision": decision.decision,
    },
    "transition": {
        "id": transition.pk,
        "objectType": transition.object_type,
        "objectId": transition.object_id,
        "fromState": transition.source_state,
        "toState": transition.target_state,
        "actorId": transition.operator_id,
        "auditReference": transition.audit_reference,
    },
    "audit": {
        "id": audit.pk,
        "actorId": audit.actor_id,
        "actionCode": audit.action_code,
        "requestIdentity": write_request.idempotency_key,
    },
    "protectedFacts": {
        "salesOrderStatus": order.status,
        "salesOrderVersion": order.version,
        "salesOrderItemId": item.pk,
        "quantity": str(item.quantity),
        "requiredDate": item.required_date.isoformat(),
        "manufacturingOutputStatus": output.release_status,
        "oeiId": oei.pk,
        "engineeringBaselineId": baseline.pk,
        "bomVersionId": bom.pk,
        "routingVersionId": routing.pk,
    },
    "planning": {
        "demandCountBefore": demand_count_before,
        "demandCountAfter": demand_count_after,
        "planningRequirementCountBefore": planning_count_before,
        "planningRequirementCountAfter": planning_count_after,
        "remainingGate": demand_gate,
        "productionDemandAdmissionReady": False,
    },
}

print(json.dumps(result, ensure_ascii=True, sort_keys=True))
