"""Workshop receipt has its own formal authority; no release-role inference."""
from dataclasses import replace
from threading import RLock

CONTRACT = "PCE-PRODUCTION-WORK-ORDER-WORKSHOP-RECEIPT-V1"
MODULE = "production-work-order"
ACTION = "production.order.receive"
READ_PERMISSION = "production.order.read"
PROCESS = "MES_PRODUCTION_OPERATION"
WORKFLOW_NODE = "PRODUCTION_WORK_ORDER_RECEIVE"
RESPONSIBILITY = "RESP_PROD_PLAN_001"
DOCUMENT_TYPE = "ProductionWorkOrder"
OBJECT = "ProductionWorkOrderWorkshopReceipt"
GET_PATH = "/api/planning/work-order-workshop-reception/"
_LOCK = RLock()
_owned_policy = None


def register_action():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned_policy
    with _LOCK:
        roles = tuple(RolePermission.objects.filter(permission__code=ACTION).order_by("role__code")
            .values_list("role__code", flat=True).distinct())
        policy = ActionPermissionPolicy(actionCode=ACTION, moduleCode=MODULE,
            requiredPermission=ACTION, role=roles, organizationScope="legal_entity",
            serverValidator="planning.work_order_workshop_receipt_service.receive_workshop_scope",
            allowedStatuses=("released",), scope="single")
        previous = POLICIES.get((MODULE, ACTION))
        if previous is not None and previous != policy:
            if previous is not _owned_policy or replace(previous, role=policy.role) != policy:
                raise RuntimeError("车间接收正式动作契约冲突，禁止覆盖。")
        POLICIES[(MODULE, ACTION)] = policy
        _owned_policy = policy
        return policy


def action_contract(work_order_id, workshop_id):
    return {**register_action().serialize(), "key": "receive", "displayName": "接收本车间工序",
        "allowedStatuses": ["not_received"], "sourceAllowedStatuses": ["released"],
        "processCode": PROCESS, "workflowNodeCode": WORKFLOW_NODE,
        "navigationNodeCode": "production-work-order", "requiredResponsibility": RESPONSIBILITY,
        "documentType": DOCUMENT_TYPE, "objectType": OBJECT,
        "assessmentSourceObjectType": DOCUMENT_TYPE, "httpMethod": "POST",
        "apiPath": f"/api/planning/work-orders/{work_order_id}/workshops/{workshop_id}/receive/",
        "readOnly": False, "executionEnabled": True, "manualExecutionSupported": True,
        "roleSelectionMode": "FORMAL_PERMISSION_HOLDER_ROLES",
        "roleAuthoritySource": "system.RolePermission", "sameRolePermissionAndScopeRequired": True}
