"""Native workshop task actions; dispatch never confers operation execution."""
from dataclasses import replace
from threading import RLock

CONTRACT = 'PCE-PRODUCTION-WORKSHOP-TASK-DISPATCH-V1'
MODULE = 'production-workshop-task'
READ_PERMISSION = 'production.task.read'
SAVE_ACTION = 'production.task.draft.save'
DISPATCH_ACTION = 'production.task.dispatch'
PROCESS = 'MES_PRODUCTION_OPERATION'
WORKFLOW_NODE = 'PRODUCTION_WORKSHOP_TASK_DISPATCH'
RESPONSIBILITY = 'RESP_PROD_TASK_DISPATCH_001'
OBJECT = 'ProductionWorkshopTask'
NUMBER_ENTITY = 'production_workshop_task'
GET_PATH = '/api/planning/workshop-tasks/'
LABELS = {SAVE_ACTION: '保存任务草稿', DISPATCH_ACTION: '正式派工'}
_lock = RLock()
_owned = {}


def register_actions():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    with _lock:
        for action, states in ((SAVE_ACTION, ('released',)), (DISPATCH_ACTION, ('draft',))):
            roles = tuple(RolePermission.objects.filter(permission__code=action).order_by('role__code')
                .values_list('role__code', flat=True).distinct())
            policy = ActionPermissionPolicy(actionCode=action, moduleCode=MODULE, requiredPermission=action,
                role=roles, organizationScope='legal_entity', serverValidator='planning.workshop_task_service.' +
                    ('save_task_draft' if action == SAVE_ACTION else 'dispatch_task'),
                allowedStatuses=states, scope='single')
            previous = POLICIES.get((MODULE, action))
            if previous is not None and previous != policy:
                if previous is not _owned.get(action) or replace(previous, role=roles) != policy:
                    raise RuntimeError('车间任务正式动作契约冲突，禁止覆盖。')
            POLICIES[(MODULE, action)] = policy
            _owned[action] = policy
        return dict(_owned)


def action_contracts(task_id=None):
    policies = register_actions()
    return {key: {**policies[action].serialize(), 'key': key, 'displayName': LABELS[action],
        'apiPath': '/api/planning/workshop-tasks/draft/' if key == 'saveDraft' else
            f'/api/planning/workshop-tasks/{task_id}/dispatch/' if task_id else None,
        'httpMethod': 'POST', 'processCode': PROCESS, 'workflowNodeCode': WORKFLOW_NODE,
        'allowedStatuses': ['not_created', 'draft'] if key == 'saveDraft' else ['draft'],
        'sourceAllowedStatuses': ['released'] if key == 'saveDraft' else ['draft'],
        'requiredResponsibility': RESPONSIBILITY, 'navigationNodeCode': 'production-workshop-task',
        'objectType': OBJECT, 'manualExecutionSupported': True, 'executionEnabled': True,
        'assessmentSourceObjectType': 'ProductionWorkOrderOperation' if key == 'saveDraft' else OBJECT,
        'sameRolePermissionAndScopeRequired': True}
        for key, action in (('saveDraft', SAVE_ACTION), ('dispatch', DISPATCH_ACTION))}
