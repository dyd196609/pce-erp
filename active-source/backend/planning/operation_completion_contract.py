"""Completion is effective only after the separate production-expeditor review."""
from dataclasses import replace
from threading import RLock

CONTRACT = 'PCE-PRODUCTION-OPERATION-COMPLETION-V1'
MODULE = 'production-operation-completion'
OBJECT = 'ProductionOperationCompletion'
BUSINESS_PROCESS = 'MES_PRODUCTION_OPERATION'
# The old work-order definition owns a different document_type.  A shared
# approval template is internal to the same MES business node, not a new menu
# or a second business-process authority.
PROCESS = 'MES_OPERATION_COMPLETION_REVIEW'
READ_PERMISSION = 'production.operation.complete.read'
REQUEST_ACTION = 'production.operation.complete.request'
APPROVE_ACTION = 'production.operation.complete.approve'
REQUEST_NODE = 'PRODUCTION_OPERATION_COMPLETE_REQUEST'
REVIEW_NODE = 'PRODUCTION_OPERATION_COMPLETE_REVIEW'
REQUEST_RESPONSIBILITY = 'RESP_PROD_OPERATION_COMPLETE_REQUEST_001'
REVIEW_RESPONSIBILITY = 'RESP_PROD_OPERATION_COMPLETE_REVIEW_001'
GET_PATH = '/api/planning/operation-completions/'
LABELS = {'': '尚未申请完工', 'unrequested': '尚未申请完工', 'pending_review': '待生产跟单员审核', 'completed': '工序完工已生效'}
_lock, _owned = RLock(), {}

def register_actions():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    with _lock:
        for action, states in ((REQUEST_ACTION, ('unrequested',)), (APPROVE_ACTION, ('pending_review',))):
            roles = tuple(RolePermission.objects.filter(permission__code=action).order_by('role__code').values_list('role__code', flat=True).distinct())
            policy = ActionPermissionPolicy(actionCode=action, moduleCode=MODULE, requiredPermission=action,
                role=roles, organizationScope='legal_entity', serverValidator='planning.operation_completion_service.execute_completion',
                allowedStatuses=states, scope='single')
            previous = POLICIES.get((MODULE, action))
            if previous is not None and previous != policy:
                if previous is not _owned.get(action) or replace(previous, role=roles) != policy:
                    raise RuntimeError('工序完工动作契约冲突，禁止覆盖。')
            POLICIES[(MODULE, action)] = policy
            _owned[action] = policy

def action_contract(key, task_id=None):
    register_actions()
    from workflow_runtime.action_permissions import POLICIES
    action, node, duty, title = (REQUEST_ACTION, REQUEST_NODE, REQUEST_RESPONSIBILITY, '提交完工申请') if key == 'request' else (APPROVE_ACTION, REVIEW_NODE, REVIEW_RESPONSIBILITY, '审核完工数据')
    return {**POLICIES[(MODULE, action)].serialize(), 'key':key, 'displayName':title,
        'apiPath':f'{GET_PATH}{task_id}/{key}/' if task_id else None, 'httpMethod':'POST',
        'processCode':PROCESS, 'businessProcessCode':BUSINESS_PROCESS, 'workflowNodeCode':node, 'requiredResponsibility':duty,
        'objectType':OBJECT, 'assessmentSourceObjectType':'ProductionWorkshopTask',
        'sameRolePermissionAndScopeRequired':True, 'requestDoesNotProveCompletion':True,
        'differentApplicantReviewerAndRoleRequired':True, 'downstreamReleaseSupported':False}
