"""Formal production putaway never borrows TEST or purchase putaway rights.

This is a software contract only. Importing it creates no permission, role,
scope, workflow, resource, inventory or enterprise release data.
"""
from workflow_runtime.action_permissions import ActionPermissionPolicy,POLICIES
from system.models import RolePermission
MODULE='production-finished-goods-handover'
PATH='/api/planning/finished-goods-handovers/'
RECEIVE='warehouse.production.putaway'
PROCESS='MES_PRODUCTION_FINISHED_GOODS_RECEIPT_FORMAL'
NODE='PRODUCTION_FINISHED_GOODS_PUTAWAY'
DUTY='RESP_WH_IO_001'
DEFINITION={'definitionCode':PROCESS,'definitionName':'正式用途生产成品接收入库职责','businessDomain':'MES',
 'documentType':'WarehouseInbound','version':1,'active':True,
 'description':'仅完整合法PRODUCTION_USE工单的真实末任务成品，独立指定仓管接收同用途WMS库存；独立开发配置不代表企业放行。'}
NODES=[{'nodeCode':NODE,'nodeName':'正式用途成品接收入库','sequence':1,'businessActionCode':RECEIVE,
 'active':True,'description':'既有仓库出入库职责、准确节点执行关系及正式生产入库权限同时满足；禁止TEST或采购权限替代。'}]
PERMISSIONS={'prepare':'production.operation.handover.prepare','dispatch':'production.operation.handover.dispatch',
 'cancel':'production.operation.handover.cancel','receive':RECEIVE,'read':'production.operation.handover.read'}
CODES={key:RECEIVE if key=='receive' else 'production.finished_goods.'+key for key in PERMISSIONS}
LABELS={'prepare':'确认整批成品备交','dispatch':'确认成品实际交出','cancel':'取消未交出成品备交',
 'receive':'确认正式用途成品接收入库','read':'读取本人正式用途成品交接'}
def action_contract(key,object_id=None):
 code=CODES[key];permission=PERMISSIONS[key]
 roles=tuple(RolePermission.objects.filter(permission__code=permission).values_list('role__code',flat=True).distinct())
 policy=ActionPermissionPolicy(actionCode=code,moduleCode=MODULE,requiredPermission=permission,role=roles,
  organizationScope='legal_entity',serverValidator='planning.finished_goods_service.execute_finished_goods',
  allowedStatuses=('open','prepared','in_transit','received','cancelled'),scope='single')
 prior=POLICIES.get((MODULE,code))
 if prior and prior.serverValidator!=policy.serverValidator:raise RuntimeError('正式成品动作身份冲突，不能覆盖。')
 POLICIES[(MODULE,code)]=policy
 path=PATH if key=='read' else PATH+'prepare/' if key=='prepare' else PATH+str(object_id)+'/'+key+'/' if object_id else None
 return {**policy.serialize(),'key':key,'displayName':LABELS[key],'apiPath':path,'httpMethod':'GET' if key=='read' else 'POST',
  'workflowProcessCode':PROCESS if key=='receive' else 'MES_OPERATION_HANDOVER','businessProcessCode':'MES_PRODUCTION_OPERATION',
  'executionEnabled':key!='read','manualExecutionSupported':True,'currentStateSource':'server'}
