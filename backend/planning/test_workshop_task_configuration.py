"""Audited isolated configuration using existing organization/role/number services."""
from django.db import transaction
from django.utils import timezone
from system.models import User,Permission,Role,RolePermission,UserRoleScopeAssignment,Position,PositionResponsibility,PositionWorkflowResponsibility,Responsibility,OrganizationOperatingAuditRecord
from system.authorization import AuthorizationService
from system.organization_operating import OrganizationOperatingService
from system.access_control_views import AccessControlFoundationView,business_hash
from masterdata.models import CodeRule
from masterdata.views import CodeRuleViewSet
from rest_framework.test import APIRequestFactory,force_authenticate
from workflow_runtime.models import WorkflowNodeDefinition
from .test_workshop_task_protocol import SAVE_ACTION,DISPATCH_ACTION,PROCESS,WORKFLOW_NODE,RESPONSIBILITY
from .test_work_order_service import _boundary
from pde.order_routing_execution_service import fail

ROLE_NAME='隔离测试车间派工员（仅测试来源）'
ENTITY='test_production_workshop_task'

def _catalog(actor):
 for code,name in ((SAVE_ACTION,'保存隔离测试车间任务'),(DISPATCH_ACTION,'派工隔离测试车间任务')):
  row=Permission.objects.filter(code=code).first()
  if row is None:
   row=Permission.objects.create(code=code,name=name,module='MES_TEST')
   OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,action_code='REGISTER_TEST_TASK_PERMISSION_CATALOG',target_type='Permission',target_id=row.pk,target_label=code,reason='本轮隔离测试动作目录，不登记正式制造权限',before_snapshot={},after_snapshot={'code':code,'module':'MES_TEST','sourcePurpose':'TEST_BUSINESS'})
  elif row.name!=name or row.module!='MES_TEST':fail('TEST_TASK_PERMISSION_CONFLICT','测试权限目录已存在不同定义，不能覆盖。')

def _position_payload(p):
 return {'positionId':p.pk,'name':p.name,'departmentId':p.department_id,'jobFamilyId':p.job_family_id,'jobLevelId':p.job_level_id,'parentPositionId':p.parent_position_id,'defaultRoleId':p.default_role_id,'description':p.description,'responsibilitySummary':p.responsibility_summary,'effectiveFrom':p.effective_from.isoformat() if p.effective_from else None,'effectiveTo':p.effective_to.isoformat() if p.effective_to else None,'active':p.is_active}

def configure(*,user,work_order_id):
 from .test_work_order_dispatch_service import _order,_groups,_fresh,protocol
 from .test_scheduling_service import _actor
 actor=_actor(user);_boundary()
 if not actor.is_superuser or not AuthorizationService.decide(user=actor,action_code='system.organization.workflow_responsibility.manage',organization_id=actor.company_id)['allowed']:fail('PERMISSION_DENIED','测试配置须由正常组织维护权限办理。')
 row=_order(actor,work_order_id);_fresh(actor,row)
 notes=[];reason='本轮隔离模拟测试配置：复用准确工序所属车间及现有车间经理，仅授予TEST来源派工，不冒称用户此前业务确认'
 with transaction.atomic():
  _catalog(actor)
  for op in row.operations.select_related('operation','work_center'):
   # Only fill a missing relation when the already-bound exact process and
   # every current active center for it prove a single identical workshop.
   center=op.work_center
   for position in Position.objects.filter(company_id=actor.company_id,process_id=op.operation_id,workshop__isnull=True,is_active=True):
    if op.operation.workshop_id!=center.workshop_id:fail('TEST_POSITION_WORKSHOP_AMBIGUOUS','工序主数据与工作中心车间归属不一致。')
    payload={**_position_payload(position),'workshopId':center.workshop_id,'reason':reason}
    result=OrganizationOperatingService.execute(user=actor,action='SAVE_POSITION',payload=payload)
    notes.append({'normalAction':'SAVE_POSITION','positionId':position.pk,'workshopId':center.workshop_id,'basisProcessId':op.operation_id,'result':result})
  view=AccessControlFoundationView()
  role=Role.objects.filter(name=ROLE_NAME).first()
  if role is None:
   value=view._save_role({'name':ROLE_NAME,'description':'仅隔离TEST工单按本人岗位所属车间保存及派工；不含正式任务、开工报工'},actor=actor,reason=reason);role=Role.objects.get(pk=value['id'])
   view._set_role_permissions({'roleId':role.pk,'permissionCodes':[SAVE_ACTION,DISPATCH_ACTION]},actor=actor,reason=reason)
  elif set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!={SAVE_ACTION,DISPATCH_ACTION}:fail('TEST_TASK_ROLE_CONFLICT','同名测试角色权限不一致。')
  duty=Responsibility.objects.get(code=RESPONSIBILITY,status='ACTIVE',is_active=True)
  node=WorkflowNodeDefinition.objects.get(node_code=WORKFLOW_NODE,process_definition__definition_code=PROCESS,active=True,business_action_code='production.task.dispatch')
  for wid,g in _groups(row).items():
   # Derive a unique current manager through the existing exact receipt-node
   # responsibility, then explicitly record the new TEST dispatch assumption.
   candidates=[]
   for uid in User.objects.filter(company_id=actor.company_id,is_active=True).values_list('pk',flat=True):
    person=User.objects.get(pk=uid)
    q,_=protocol._qualification(person,row,g['workshop'],source_ok=True)
    if q['ready']:candidates.append((person,q['currentActorEvidence']))
   if len(candidates)!=1:fail('TEST_TASK_MANAGER_AMBIGUOUS','现有同车间接收经理不唯一，须集中裁决，未自动指定。')
   person,evidence=candidates[0];position=Position.objects.get(pk=evidence['positionId'])
   rel=PositionResponsibility.objects.filter(position=position,responsibility=duty).first()
   if rel is None:
    OrganizationOperatingService.execute(user=actor,action='SAVE_POSITION_RESPONSIBILITY',request_identity=f'TEST-TASK-DUTY:{position.pk}:{duty.pk}',payload={'positionId':position.pk,'responsibilityId':duty.pk,'active':True,'isPrimary':False,'reason':reason})
   mapping=PositionWorkflowResponsibility.objects.filter(position=position,responsibility=duty,workflow_node=node,ownership_type='OWNER',active=True).first()
   if mapping is None:
    OrganizationOperatingService.execute(user=actor,action='SAVE_WORKFLOW_RESPONSIBILITY',payload={'positionId':position.pk,'responsibilityId':duty.pk,'workflowNodeId':node.pk,'ownershipType':'OWNER','active':True,'effectiveFrom':timezone.now().date().isoformat(),'reason':reason})
   if not UserRoleScopeAssignment.objects.filter(user=person,role=role,organization_id=actor.company_id,active=True).exists():
    value={'roleCode':role.code,'legalEntityId':str(actor.company_id),'departmentId':None,'scopeCode':'ORGANIZATION','version':1}
    assignment=UserRoleScopeAssignment.objects.create(user=person,role=role,organization_id=actor.company_id,department_id=None,scope_code='ORGANIZATION',active=True,version=1,business_hash=business_hash(value))
    OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,action_code='APPEND_ISOLATED_TEST_TASK_AUTHORITY',target_type='UserRoleScopeAssignment',target_id=assignment.pk,target_label=person.username,reason=reason,before_snapshot={},after_snapshot={**value,'userId':person.pk,'workshopId':wid,'allowedTestActions':[SAVE_ACTION,DISPATCH_ACTION],'formalAuthorityGranted':False})
   notes.append({'workshopId':wid,'dispatcherUserId':person.pk,'positionId':position.pk,'testAssumption':'本轮测试派工经理沿现有唯一接收职责配置；实际工序人员另由资源服务确定'})
  if not CodeRule.objects.filter(company_id=actor.company_id,entity_type=ENTITY).exists():
   request=APIRequestFactory().post('/api/masterdata/code-rules/',{'entity_type':ENTITY,'prefix':'TEST-WT-','date_format':'%Y%m','seq_length':6,'current_seq':0,'company_id':actor.company_id},format='json');force_authenticate(request,user=actor)
   response=CodeRuleViewSet.as_view({'post':'create'})(request)
   if response.status_code!=201:fail('TEST_TASK_NUMBER_RULE_FAILED',str(response.data))
 return {'normalServices':'OrganizationOperatingService,AccessControlFoundationView,CodeRuleViewSet; audited non-destructive test authority append','notes':notes,'onlyTestActionPermissions':[SAVE_ACTION,DISPATCH_ACTION]}
