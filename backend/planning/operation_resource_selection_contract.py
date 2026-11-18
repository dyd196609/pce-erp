

# Native formal continuation: individually restored symbols; existing proofs preserved.
from dataclasses import replace

from threading import RLock

from .work_order_workshop_receipt_contract import (MODULE, PROCESS, WORKFLOW_NODE, RESPONSIBILITY,
    READ_PERMISSION, ACTION as REQUIRED_PERMISSION)

CONTRACT = 'PCE-PRODUCTION-OPERATION-RESOURCE-SELECTION-V1'

GET_PATH = '/api/planning/operation-resources/'

SELECT_ACTION = 'production.order.select_operation_resource'

RECEIVE_ACTION = 'production.order.receive_operation'

SELECT_OBJECT = 'ProductionOperationResourceSelection'

RECEIVE_OBJECT = 'ProductionOperationPreciseReceipt'

SUPPLEMENT_OBJECT = 'ProductionWorkshopReceiptSupplement'

ANCHOR_KIND = 'PCE-PRECISE-OPERATION-RECEIPT-ANCHOR-V1'

NAMESPACE = 'MES_OPERATION_RESOURCE_AUTHORITY'

_lock, _owned = RLock(), {}

def register_actions():
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    with _lock:
        roles=tuple(RolePermission.objects.filter(permission__code=REQUIRED_PERMISSION)
            .order_by('role__code').values_list('role__code',flat=True).distinct())
        result={}
        for key,action in (('selectResource',SELECT_ACTION),('receiveOperation',RECEIVE_ACTION)):
            policy=ActionPermissionPolicy(actionCode=action,moduleCode=MODULE,requiredPermission=REQUIRED_PERMISSION,
                role=roles,organizationScope='legal_entity',scope='single',allowedStatuses=('released',),
                serverValidator='planning.operation_resource_selection_service.'+('select_operation_resource' if key=='selectResource' else 'receive_operation'))
            old=POLICIES.get((MODULE,action))
            if old is not None and old!=policy and (old is not _owned.get(action) or replace(old,role=roles)!=policy):
                raise RuntimeError('正式资源选择／精确接收动作契约冲突，禁止覆盖。')
            POLICIES[(MODULE,action)]=policy;_owned[action]=policy;result[key]=policy
        return result

def action_contract(key, operation_id=None):
    policy=register_actions()[key]
    select=key=='selectResource'
    return {**policy.serialize(),'key':key,'displayName':'正式选择执行资源' if select else '确认本工序精确接收',
        'processCode':PROCESS,'workflowNodeCode':WORKFLOW_NODE,'navigationNodeCode':MODULE,
        'requiredResponsibility':RESPONSIBILITY,'objectType':SELECT_OBJECT if select else RECEIVE_OBJECT,
        'assessmentSourceObjectType':'ProductionWorkOrderOperation','authorityActionCode':REQUIRED_PERMISSION,
        'httpMethod':'POST','apiPath':GET_PATH+str(operation_id)+('/select/' if select else '/receive/') if operation_id else None,
        'sameRolePermissionAndScopeRequired':True,'noAdditionalApprovalLayer':True,
        'readOnly':False,'executionEnabled':True,'manualExecutionSupported':True}
