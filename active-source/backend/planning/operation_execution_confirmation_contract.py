"""Actual-passage registration reuses the existing reporting authority."""
from dataclasses import replace
from threading import RLock
from .operation_report_contract import MODULE, PROCESS, WORKFLOW_NODE, RESPONSIBILITY, REPORT_ACTION

CONTRACT = 'PCE-PRODUCTION-OPERATION-EXECUTION-CONFIRMATION-V1'
OBJECT = 'ProductionOperationExecutionConfirmation'
ACTION = 'production.operation.confirm_execution'
REQUIRED_PERMISSION = REPORT_ACTION
_lock, _owned = RLock(), None

def register_action():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    global _owned
    with _lock:
        roles=tuple(RolePermission.objects.filter(permission__code=REQUIRED_PERMISSION).order_by('role__code')
            .values_list('role__code',flat=True).distinct())
        policy=ActionPermissionPolicy(actionCode=ACTION,moduleCode=MODULE,requiredPermission=REQUIRED_PERMISSION,
            role=roles,organizationScope='legal_entity',scope='single',allowedStatuses=('unconfirmed',),
            serverValidator='planning.operation_execution_confirmation_service.confirm_execution')
        old=POLICIES.get((MODULE,ACTION))
        if old is not None and old != policy and (old is not _owned or replace(old,role=roles) != policy):
            raise RuntimeError('实际经过登记动作合同冲突，禁止覆盖。')
        POLICIES[(MODULE,ACTION)]=policy;_owned=policy
        return policy

def action_contract(task_id=None):
    return {**register_action().serialize(),'key':'confirmExecution','displayName':'登记实际经过',
        'apiPath':f'/api/planning/operation-reports/{task_id}/confirm-execution/' if task_id else None,
        'httpMethod':'POST','processCode':PROCESS,'workflowNodeCode':WORKFLOW_NODE,'requiredResponsibility':RESPONSIBILITY,
        'navigationNodeCode':MODULE,'objectType':OBJECT,'assessmentSourceObjectType':'ProductionWorkshopTask',
        'authorityActionCode':REQUIRED_PERMISSION,'sameRolePermissionAndScopeRequired':True,'assigneeSelfOnly':True,
        'manualExecutionSupported':True,'executionEnabled':True,'quantityApplicable':False}
