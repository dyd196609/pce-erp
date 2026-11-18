"""V2 qualification and manual intent contract; registration never executes."""

from dataclasses import replace
from threading import RLock

CONTRACT = "PCE-PRODUCTION-WORK-ORDER-RELEASE-ADMISSION-V2"
MODULE = "production-work-order"
ACTION = "production.order.release"
GENERATE_ACTION = "production.order.generate"
RESPONSIBILITY = "RESP_PMC_PLAN_001"
PROCESS = "MES_PRODUCTION_OPERATION"
WORKFLOW_NODE = "PRODUCTION_WORK_ORDER_RELEASE"
NAVIGATION_NODE = "production-work-order"
DOCUMENT_TYPE = "ProductionWorkOrder"
# Existing confirmed/approved manufacturing states, including partial delivery.
# Completed orders are terminal for this admission; no order state is changed.
ALLOWED_ORDER_STATES = ("approved", "confirmed", "engineering", "manufacturing_ready", "in_progress", "delivering")
_POLICY_LOCK = RLock()
_owned_policy = None
_owned_generate_policy = None


def register_actions():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned_policy, _owned_generate_policy
    with _POLICY_LOCK:
        # This is the global formal permission directory, never an actor's role
        # list. An empty directory remains empty and fails the shared role gate.
        role_codes = tuple(RolePermission.objects.filter(permission__code=ACTION)
            .order_by("role__code").values_list("role__code", flat=True).distinct())
        policy = ActionPermissionPolicy(actionCode=ACTION, moduleCode=MODULE,
            requiredPermission=ACTION, role=role_codes, organizationScope="legal_entity",
            serverValidator="planning.work_order_release_admission_service.assess_release_admission",
            allowedStatuses=("confirmed",), scope="single")
        key = (MODULE, ACTION)
        existing = POLICIES.get(key)
        if existing is not None and existing != policy:
            if existing is not _owned_policy or replace(existing, role=policy.role) != policy:
                raise RuntimeError("生产工单下达动作契约冲突，禁止覆盖已有注册。")
        POLICIES[key] = policy
        _owned_policy = policy
        generation = replace(policy, actionCode=GENERATE_ACTION,
            serverValidator="planning.work_order_execution_service.generate_work_order")
        generation_key = (MODULE, GENERATE_ACTION)
        previous = POLICIES.get(generation_key)
        if previous is not None and previous != generation:
            if previous is not _owned_generate_policy or replace(previous, role=generation.role) != generation:
                raise RuntimeError("生产工单生成动作契约冲突，禁止覆盖已有注册。")
        POLICIES[generation_key] = generation
        _owned_generate_policy = generation
        return policy


def action_contract():
    return {**register_actions().serialize(), "displayName": "生产工单下达资格",
        "processCode": PROCESS, "workflowNodeCode": WORKFLOW_NODE,
        "navigationNodeCode": NAVIGATION_NODE, "requiredResponsibility": RESPONSIBILITY,
        "documentType": DOCUMENT_TYPE, "objectType": DOCUMENT_TYPE,
        "assessmentSourceObjectType": "ProductionPlan", "objectAlreadyExists": False,
        "readOnly": False, "executionEnabled": True, "qualificationReadOnly": True,
        "manualExecutionSupported": True, "executionAvailabilitySource": "execution.availableActions",
        "roleSelectionMode": "FORMAL_PERMISSION_HOLDER_ROLES",
        "roleAuthoritySource": "system.RolePermission", "sameRolePermissionAndScopeRequired": True,
        "allowedOrderStates": list(ALLOWED_ORDER_STATES)}
