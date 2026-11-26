

# Native formal continuation: individually restored symbols; existing proofs preserved.
from dataclasses import replace

from threading import RLock

CONTRACT = 'PCE-PRODUCTION-OPERATION-RESOURCE-HANDOFF-V1'

MODULE = 'production-work-order'

OBJECT = 'ProductionOperationResourceHandoff'

ACTION = 'production.order.resource_handoff'

REQUIRED_PERMISSION = 'production.order.receive'

PROCESS = 'MES_PRODUCTION_OPERATION'

WORKFLOW_NODE = 'PRODUCTION_WORK_ORDER_RECEIVE'

RESPONSIBILITY = 'RESP_PROD_PLAN_001'

GET_PATH = '/api/planning/resource-handoffs/'

NAMESPACE = 'MES_OPERATION_RESOURCE_HANDOFF'

_lock, _owned = RLock(), None

def register_action():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned
    with _lock:
        roles = tuple(RolePermission.objects.filter(permission__code=REQUIRED_PERMISSION)
            .order_by('role__code').values_list('role__code', flat=True).distinct())
        policy = ActionPermissionPolicy(actionCode=ACTION, moduleCode=MODULE,
            requiredPermission=REQUIRED_PERMISSION, role=roles, organizationScope='legal_entity',
            serverValidator='planning.operation_resource_handoff_service.confirm_resource_handoff',
            allowedStatuses=('released',), scope='single')
        previous = POLICIES.get((MODULE, ACTION))
        if previous is not None and previous != policy:
            if previous is not _owned or replace(previous, role=roles) != policy:
                raise RuntimeError('工序资源归属承接动作契约冲突，禁止覆盖。')
        POLICIES[(MODULE, ACTION)] = policy
        _owned = policy
        return policy

def action_contract(operation_id=None):
    return {**register_action().serialize(), 'key': 'confirm', 'displayName': '确认本工序归属承接',
        'processCode': PROCESS, 'workflowNodeCode': WORKFLOW_NODE,
        'requiredResponsibility': RESPONSIBILITY, 'objectType': OBJECT,
        'assessmentSourceObjectType': 'ProductionWorkOrderOperation',
        'authorityActionCode': REQUIRED_PERMISSION, 'httpMethod': 'POST',
        'apiPath': f'{GET_PATH}{operation_id}/confirm/' if operation_id else None,
        'sameRolePermissionAndScopeRequired': True,
        'doesNotReplaceOriginalReceipt': True, 'requiresTargetWorkshopReceiver': True,
        'noAdditionalApprovalLayer': True}
