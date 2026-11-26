"""Native, assignee-only operation start; reporting is a separate closed boundary."""
from dataclasses import replace
from threading import RLock

CONTRACT = 'PCE-PRODUCTION-OPERATION-START-V1'
MODULE = 'production-operation-start'
READ_PERMISSION = 'production.operation.read'
START_ACTION = 'production.operation.start'
PROCESS = 'MES_PRODUCTION_OPERATION'
WORKFLOW_NODE = 'PRODUCTION_OPERATION_START'
RESPONSIBILITY = 'RESP_PROD_OPERATION_START_001'
OBJECT = 'ProductionOperationStart'
GET_PATH = '/api/planning/operation-starts/'
_lock = RLock()
_owned = None


def register_action():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned
    with _lock:
        roles = tuple(RolePermission.objects.filter(permission__code=START_ACTION).order_by('role__code')
            .values_list('role__code', flat=True).distinct())
        policy = ActionPermissionPolicy(actionCode=START_ACTION, moduleCode=MODULE,
            requiredPermission=START_ACTION, role=roles, organizationScope='legal_entity',
            serverValidator='planning.operation_start_service.start_operation',
            allowedStatuses=('waiting',), scope='single')
        previous = POLICIES.get((MODULE, START_ACTION))
        if previous is not None and previous != policy:
            if previous is not _owned or replace(previous, role=roles) != policy:
                raise RuntimeError('正式工序开工动作契约冲突，禁止覆盖。')
        POLICIES[(MODULE, START_ACTION)] = policy
        _owned = policy
        return policy


def action_contract(task_id=None):
    return {**register_action().serialize(), 'key': 'start', 'displayName': '开工',
        'apiPath': f'/api/planning/operation-starts/{task_id}/start/' if task_id else None,
        'httpMethod': 'POST', 'processCode': PROCESS, 'workflowNodeCode': WORKFLOW_NODE,
        'requiredResponsibility': RESPONSIBILITY, 'allowedStatuses': ['waiting'],
        'navigationNodeCode': MODULE, 'objectType': OBJECT,
        'assessmentSourceObjectType': 'ProductionWorkshopTask',
        'sameRolePermissionAndScopeRequired': True, 'assigneeSelfOnly': True,
        'manualExecutionSupported': True, 'executionEnabled': True}
