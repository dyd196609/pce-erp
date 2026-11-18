from django.utils import timezone
from .finished_goods_contract import RECEIVE,PROCESS,NODE,DUTY,DEFINITION,NODES,MODULE,action_contract,CODES,PERMISSIONS
from .operation_handover_core import actor_for,qualify,fail
from .mes_test_source_bridge import _employees,_effective,_authority,_assert_hash
from system.models import PositionResponsibility,PositionWorkflowResponsibility
from workflow_runtime.models import ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator
from pde.work_center_responsibility_service import ObjectFacts
from workflow_runtime.definition_service import _canonical_hash

def warehouse_qualification(actor,object_id=None,status='open',required=True,*,purpose='TEST_BUSINESS'):
 if purpose=='PRODUCTION_USE':
  from .finished_goods_formal_contract import RECEIVE,PROCESS,NODE,DUTY,DEFINITION,NODES
 elif purpose=='TEST_BUSINESS':
  from .finished_goods_contract import RECEIVE,PROCESS,NODE,DUTY,DEFINITION,NODES
 else:fail('FINISHED_GOODS_PURPOSE_REQUIRED','须引用本单明确用途，不能借用其他用途入库合同。',403)
 purpose_label='正式用途生产' if purpose=='PRODUCTION_USE' else '测试生产'
 employee,position,department,_,evidence=_employees(actor);issues=[]
 today=timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
 if actor.is_superuser:issues.append('不得用管理员替代明确指定的实际仓管接收身份。')
 employment=bool(employee and position and department and _effective(position,today) and _effective(department,today)
  and position.department_id==department.pk and position.company_id==department.company_id==actor.company_id
  and (employee.hire_date is None or employee.hire_date<=today)
  and (employee.leave_date is None or employee.leave_date>today)
  and (employee.resignation_date is None or employee.resignation_date>today))
 if not employment:issues.append('须有唯一有效在职员工及同公司岗位部门。')
 definition=ProcessDefinition.objects.filter(definition_code=PROCESS,active=True,document_type=DEFINITION['documentType']).first()
 node=definition.nodes.filter(node_code=NODE,business_action_code=RECEIVE,active=True).first() if definition else None
 if definition:
  _assert_hash(definition)
 if not definition or definition.definition_hash!=_canonical_hash({**DEFINITION,'nodes':NODES}) or not node:
  issues.append(purpose_label+'成品接收职责节点尚未按真实合同配置。')
 duties=list(PositionResponsibility.objects.filter(position=position,active=True,responsibility__code=DUTY,
  responsibility__status='ACTIVE',responsibility__is_active=True).select_related('responsibility')) if employment else []
 duty=duties[0] if len(duties)==1 and _effective(duties[0].responsibility,today) else None
 mappings=list(PositionWorkflowResponsibility.objects.filter(position=position,responsibility=duty.responsibility,
  workflow_node=node,workflow_code=PROCESS,node_code=NODE,ownership_type='EXECUTOR',active=True)) if duty and node else []
 mapping=mappings[0] if len(mappings)==1 and _effective(mappings[0],today) else None
 if not mapping:issues.append('须保留既有仓库出入库职责及本动作准确执行关系。')
 allowed,matched,native=_authority(actor,RECEIVE,department.pk if department else None,actor.pk)
 contract=action_contract('receive',object_id,purpose=purpose);fact_id=object_id or actor.company_id
 decision=ActionPermissionValidator(fact_provider=ObjectFacts(actor,MODULE,fact_id,status)).evaluate(user=actor,
  module_code=MODULE,action_code=RECEIVE,object_ids=[fact_id],selection_count=1,requested_legal_entity_id=str(actor.company_id))
 if not allowed or not decision['granted']:issues.append('缺少同一角色的'+purpose_label+'入库动作及当前公司范围。')
 evidence.update(positionResponsibilityId=duty.pk if duty else None,responsibilityId=duty.responsibility_id if duty else None,
  workflowResponsibilityId=mapping.pk if mapping else None,workflowNodeId=node.pk if node else None,
  workflowProcessCode=PROCESS,workflowNodeCode=NODE,responsibilityCode=DUTY,ownershipType='EXECUTOR',matchedAuthorityEvidence=matched)
 q={'ready':not issues,'missingItems':issues,'statusLabel':'指定仓管接收资格已核实' if not issues else '；'.join(issues),
  'currentActorEvidence':evidence,'authorization':native,'actionPermissionDecision':decision,'actionContract':contract,
  'roleCodes':sorted({x['roleCode'] for x in matched}),'definitionId':definition.pk if definition else None,'nodeId':node.pk if node else None}
 if required and issues:fail('FINISHED_GOODS_WAREHOUSE_DENIED',q['statusLabel'],403)
 return q

def source_qualification(actor,key,task,object_id=None,status='open',required=True):
 # This reuses the precise WC/duty/role capability, not an OperationHandover
 # document's state machine. FG has its own actual state contract below and
 # execute_finished_goods enforces its transition/version and original intent.
 # In particular, a received FG remains readable/replayable by its real sender.
 q=qualify(actor,PERMISSIONS[key],task.work_center_id,'ProductionFinishedGoodsTransfer',object_id,'open',required=False)
 contract=action_contract(key,object_id,purpose=task.work_order.usage_purpose);fact_id=object_id or task.pk
 decision=ActionPermissionValidator(fact_provider=ObjectFacts(actor,MODULE,fact_id,status)).evaluate(user=actor,
  module_code=MODULE,action_code=CODES[key],object_ids=[fact_id],selection_count=1,requested_legal_entity_id=str(actor.company_id))
 issues=q['missingItems'][:]
 if not decision['granted']:issues.append('缺少成品交接同角色动作及公司范围。')
 if task.assignment_snapshot.get('userId')!=actor.pk or task.execution_employee_id!=q['currentActorEvidence'].get('employeeId'):
  issues.append('只允许真实获派末道任务的本人班组长办理。')
 q={**q,'ready':not issues,'missingItems':issues,'statusLabel':'末道本人交接资格已核实' if not issues else '；'.join(issues),
  'actionContract':contract,'actionPermissionDecision':decision}
 if required and issues:fail('FINISHED_GOODS_SOURCE_DENIED',q['statusLabel'],403)
 return q
