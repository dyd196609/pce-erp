"""Independent, assignee-only partial reporting action contract."""
from dataclasses import replace
from threading import RLock

CONTRACT = 'PCE-PRODUCTION-OPERATION-REPORT-V1'
MODULE = 'production-operation-report'
READ_PERMISSION = 'production.operation.report.read'
REPORT_ACTION = 'production.operation.report'
PROCESS = 'MES_PRODUCTION_OPERATION'
WORKFLOW_NODE = 'PRODUCTION_OPERATION_REPORT'
RESPONSIBILITY = 'RESP_PROD_OPERATION_REPORT_001'
OBJECT = 'ProductionOperationReport'
GET_PATH = '/api/planning/operation-reports/'
_lock = RLock()
_owned = None


def register_action():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned
    with _lock:
        roles = tuple(RolePermission.objects.filter(permission__code=REPORT_ACTION).order_by('role__code')
            .values_list('role__code', flat=True).distinct())
        policy = ActionPermissionPolicy(actionCode=REPORT_ACTION, moduleCode=MODULE,
            requiredPermission=REPORT_ACTION, role=roles, organizationScope='legal_entity',
            serverValidator='planning.operation_report_service.report_operation',
            allowedStatuses=('open',), scope='single')
        previous = POLICIES.get((MODULE, REPORT_ACTION))
        if previous is not None and previous != policy:
            if previous is not _owned or replace(previous, role=roles) != policy:
                raise RuntimeError('正式工序报工动作契约冲突，禁止覆盖。')
        POLICIES[(MODULE, REPORT_ACTION)] = policy
        _owned = policy
        return policy


def action_contract(task_id=None):
    return {**register_action().serialize(), 'key': 'report', 'displayName': '提交本次报工',
        'apiPath': f'/api/planning/operation-reports/{task_id}/report/' if task_id else None,
        'httpMethod': 'POST', 'processCode': PROCESS, 'workflowNodeCode': WORKFLOW_NODE,
        'requiredResponsibility': RESPONSIBILITY, 'allowedStatuses': ['open'],
        'navigationNodeCode': MODULE, 'objectType': OBJECT,
        'assessmentSourceObjectType': 'ProductionWorkshopTask',
        'sameRolePermissionAndScopeRequired': True, 'assigneeSelfOnly': True,
        'manualExecutionSupported': True, 'executionEnabled': True}
