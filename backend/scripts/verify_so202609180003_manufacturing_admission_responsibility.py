"""Read-only final verification for SO202609180003 manufacturing admission responsibility."""

import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
os.environ["PCE_DATABASE_PATH"] = str(DATABASE)

from django.conf import settings

settings.DATABASES["default"]["NAME"] = f"file:{DATABASE.as_posix()}?mode=ro"
settings.DATABASES["default"]["OPTIONS"] = {"uri": True}

import django

django.setup()

from django.db import connection

from planning.models import Demand, PlanningRequirement
from sales.models import SalesOrder, SalesOrderItem
from system.authorization import AuthorizationService
from system.models import (
    Permission,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.execution_resolution import WorkflowExecutionResolutionService
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
    WorkflowNodeDefinition,
)
from pde.models import BOMVersion, ProductManufacturingOutput, RoutingVersion


def file_hash():
    return hashlib.sha256(DATABASE.read_bytes()).hexdigest().upper()


with connection.cursor() as cursor:
    cursor.execute("PRAGMA query_only=ON")
    cursor.execute("PRAGMA quick_check(1)")
    integrity = cursor.fetchone()[0]

before_hash = file_hash()
order = SalesOrder.objects.get(pk=3, order_no="SO202609180003")
item = SalesOrderItem.objects.get(pk=3, sales_order=order)
responsible_user = User.objects.get(pk=30, username="pce_emp_comp001_0001")
employee = responsible_user.employee_profile
permission = Permission.objects.get(pk=139, code="pde.order.manufacturing_admission.confirm")
role = Role.objects.get(pk=40, code="manufacturing_admission_approver")
role_permission = RolePermission.objects.get(pk=350, role=role, permission=permission)
scope = UserRoleScopeAssignment.objects.get(
    pk=68, user=responsible_user, role=role, organization_id=1
)
responsibility = Responsibility.objects.get(
    pk=63, code="MANUFACTURING_ADMISSION_APPROVER"
)
position_responsibility = PositionResponsibility.objects.get(
    pk=181, position_id=30, responsibility=responsibility
)
definition = ProcessDefinition.objects.get(
    pk=10, definition_code="ORDER_MANUFACTURING_ADMISSION"
)
node = WorkflowNodeDefinition.objects.get(
    pk=48, process_definition=definition, node_code="MANUFACTURING_ADMISSION_CONFIRM"
)
workflow_responsibility = PositionWorkflowResponsibility.objects.get(
    pk=46,
    position_id=30,
    responsibility=responsibility,
    workflow_node=node,
    ownership_type="APPROVER",
)
admin = User.objects.get(pk=1)
resolution = WorkflowExecutionResolutionService.resolve(
    user=admin, definition_id=definition.pk
)
node_resolution = resolution["nodes"][0]
resolved_account = next(
    row for row in node_resolution["accounts"] if row["id"] == responsible_user.pk
)
decision = AuthorizationService.decide(
    user=responsible_user,
    action_code=permission.code,
    organization_id="1",
    business_object={"departmentId": 15, "ownerUserId": responsible_user.pk},
)

facts = {
    "database": {
        "path": str(DATABASE),
        "mode": "mode=ro + PRAGMA query_only=ON",
        "integrity": integrity,
        "sha256Before": before_hash,
    },
    "order": {
        "id": order.pk,
        "orderNo": order.order_no,
        "status": order.status,
        "version": order.version,
        "createdById": order.created_by_id,
        "approvedById": order.approved_by_id,
        "confirmedById": order.confirmed_by_id,
        "itemId": item.pk,
    },
    "responsiblePerson": {
        "userId": responsible_user.pk,
        "username": responsible_user.username,
        "accountActive": responsible_user.is_active,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "employeeStatus": employee.status,
        "departmentId": employee.department_ref_id,
        "positionId": employee.position_ref_id,
        "segregatedFromCreator": responsible_user.pk != order.created_by_id,
    },
    "configuration": {
        "permissionId": permission.pk,
        "roleId": role.pk,
        "rolePermissionId": role_permission.pk,
        "scopeAssignmentId": scope.pk,
        "scopeCode": scope.scope_code,
        "responsibilityId": responsibility.pk,
        "responsibilityStatus": responsibility.status,
        "positionResponsibilityId": position_responsibility.pk,
        "processDefinitionId": definition.pk,
        "processCode": definition.definition_code,
        "processName": definition.definition_name,
        "documentType": definition.document_type,
        "nodeId": node.pk,
        "nodeCode": node.node_code,
        "workflowResponsibilityId": workflow_responsibility.pk,
        "ownershipType": workflow_responsibility.ownership_type,
        "authorizationDecision": decision["decisionCode"],
        "executorResolved": resolved_account["executable"],
        "resolutionIssueCodes": node_resolution["issueCodes"],
    },
    "confirmationExecution": {
        "workflowInstanceCount": WorkflowInstance.objects.filter(
            process_definition=definition, document_id=order.pk
        ).count(),
        "approvalTaskCount": ApprovalTask.objects.filter(
            workflow_instance__process_definition=definition,
            workflow_instance__document_id=order.pk,
        ).count(),
        "approvalDecisionCount": ApprovalDecision.objects.filter(
            task__workflow_instance__process_definition=definition,
            task__workflow_instance__document_id=order.pk,
        ).count(),
        "salesOrderTransitionCount": BusinessStateTransition.objects.filter(
            object_type="SalesOrder", object_id=order.pk
        ).count(),
        "status": "NOT_EXECUTED",
    },
    "protectedData": {
        "manufacturingOutputId1Exists": ProductManufacturingOutput.objects.filter(pk=1).exists(),
        "bomVersionId3Exists": BOMVersion.objects.filter(pk=3).exists(),
        "routingVersionId43Exists": RoutingVersion.objects.filter(pk=43).exists(),
        "demandTotal": Demand.objects.count(),
        "demandForOrder": Demand.objects.filter(sales_order_item__sales_order=order).count(),
        "planningRequirementTotal": PlanningRequirement.objects.count(),
        "planningRequirementForOrder": PlanningRequirement.objects.filter(
            demand__sales_order_item__sales_order=order
        ).count(),
    },
}

assert integrity == "ok"
assert order.status == "draft" and order.created_by_id == 11
assert order.approved_by_id is None and order.confirmed_by_id is None
assert item.pk == 3
assert employee.employee_no == "EMP-COMP001-0001" and employee.status == "active"
assert responsible_user.is_active and responsible_user.company_id == 1
assert responsible_user.pk != order.created_by_id
assert scope.active and scope.scope_code == "ORGANIZATION" and scope.department_id is None
assert responsibility.status == "ACTIVE" and responsibility.is_active
assert position_responsibility.active and workflow_responsibility.active
assert definition.active and node.active and node.business_action_code == permission.code
assert decision["allowed"] and resolved_account["executable"]
assert not node_resolution["issueCodes"]
assert facts["confirmationExecution"]["workflowInstanceCount"] == 0
assert facts["confirmationExecution"]["approvalTaskCount"] == 0
assert facts["confirmationExecution"]["approvalDecisionCount"] == 0
assert facts["confirmationExecution"]["salesOrderTransitionCount"] == 0
assert facts["protectedData"]["demandForOrder"] == 0
assert facts["protectedData"]["planningRequirementForOrder"] == 0

facts["database"]["sha256After"] = file_hash()
facts["database"]["unchangedByVerification"] = (
    facts["database"]["sha256Before"] == facts["database"]["sha256After"]
)
assert facts["database"]["unchangedByVerification"]
print(json.dumps(facts, ensure_ascii=False, indent=2, default=str))
