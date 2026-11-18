from workflow_runtime.action_permissions import ActionPermissionPolicy,POLICIES
from system.models import RolePermission

MODULE='production-finished-goods-handover'
PATH='/api/planning/finished-goods-handovers/'
RECEIVE='warehouse.production.test_putaway'
PROCESS='MES_PRODUCTION_FINISHED_GOODS_RECEIPT'
NODE='TEST_PRODUCTION_FINISHED_GOODS_PUTAWAY'
DUTY='RESP_WH_IO_001'
DEFINITION={'definitionCode':PROCESS,'definitionName':'测试生产成品接收入库职责','businessDomain':'MES',
 'documentType':'ProductionFinishedGoodsTransfer','version':1,'active':True,
 'description':'已独审生产执行的TEST成品整批交接与原生WMS入库；不创建采购或正式生产资格。'}
NODES=[{'nodeCode':NODE,'nodeName':'测试生产成品接收入库','sequence':1,'businessActionCode':RECEIVE,
 'active':True,'description':'明确指定的仓管员按同用途来源、仓及库位确认实际收讫与WMS入库。'}]
PERMISSIONS={'prepare':'production.operation.handover.prepare','dispatch':'production.operation.handover.dispatch',
 'cancel':'production.operation.handover.cancel','receive':RECEIVE,'read':'production.operation.handover.read'}
CODES={key:RECEIVE if key=='receive' else 'production.finished_goods.'+key for key in PERMISSIONS}
LABELS={'prepare':'确认整批成品备交','dispatch':'确认成品实际交出','cancel':'取消未交出成品备交',
 'receive':'确认整批成品接收并测试入库','read':'读取本人测试成品交接'}
def codes_for(purpose):
 if purpose=='PRODUCTION_USE':
  from .finished_goods_formal_contract import CODES as formal_codes
  return formal_codes
 if purpose!='TEST_BUSINESS':raise ValueError('成品动作必须有准确原生用途。')
 return CODES

def action_contract(key,object_id=None,*,purpose='TEST_BUSINESS'):
 if purpose=='PRODUCTION_USE':
  from .finished_goods_formal_contract import action_contract as formal_contract
  return formal_contract(key,object_id)
 if purpose!='TEST_BUSINESS':raise ValueError('成品动作必须有准确原生用途。')
 code=CODES[key];permission=PERMISSIONS[key];roles=tuple(RolePermission.objects.filter(permission__code=permission).values_list('role__code',flat=True).distinct())
 policy=ActionPermissionPolicy(actionCode=code,moduleCode=MODULE,requiredPermission=permission,role=roles,
  organizationScope='legal_entity',serverValidator='planning.finished_goods_service.execute_finished_goods',
  allowedStatuses=('open','prepared','in_transit','received','cancelled'),scope='single')
 prior=POLICIES.get((MODULE,code))
 if prior and prior.serverValidator!=policy.serverValidator:raise RuntimeError('成品交接动作合同冲突，不能覆盖既有权限。')
 POLICIES[(MODULE,code)]=policy
 path=PATH if key=='read' else PATH+'prepare/' if key=='prepare' else PATH+str(object_id)+'/'+key+'/' if object_id else None
 return {**policy.serialize(),'key':key,'displayName':LABELS[key],'apiPath':path,'httpMethod':'GET' if key=='read' else 'POST',
  'workflowProcessCode':PROCESS if key=='receive' else 'MES_OPERATION_HANDOVER','businessProcessCode':'MES_PRODUCTION_OPERATION',
  'executionEnabled':key!='read','manualExecutionSupported':True,'currentStateSource':'server'}
