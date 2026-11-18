"""Minimum audited TEST-start authority for a real frozen assignee."""
from django.db import transaction
from system.models import Permission,Role,RolePermission,UserRoleScopeAssignment,OrganizationOperatingAuditRecord,User,PositionResponsibility,PositionWorkflowResponsibility,Responsibility
from system.access_control_views import AccessControlFoundationView,business_hash
from system.organization_operating import OrganizationOperatingService
from workflow_runtime.models import WorkflowNodeDefinition
from . import test_operation_start_protocol as native
from .test_operation_start_service import _boundary
from .workshop_task_models import ProductionWorkshopTask
from pde.order_routing_execution_service import fail

@transaction.atomic
def configure(*,user,task_ids):
 _boundary()
 if not user.is_superuser:fail('PERMISSION_DENIED','须正常组织权限管理员维护隔离测试开工职责。')
 reason='本轮隔离测试开工最小授权：仅本人冻结任务，不授予正式开工、报工或完工权限'
 for code,name in [(native.READ_PERMISSION,'本人测试任务开工查看'),(native.START_ACTION,'本人隔离测试工序开工')]:
  p,created=Permission.objects.get_or_create(code=code,defaults={'name':name,'module':'MES_TEST'})
  if p.module!='MES_TEST' or p.name!=name:fail('TEST_START_PERMISSION_CONFLICT','同码测试权限定义不同。')
  if created:OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='REGISTER_TEST_START_PERMISSION',target_type='Permission',target_id=p.pk,target_label=code,reason=reason,before_snapshot={},after_snapshot={'code':code,'module':'MES_TEST','configurationOnly':True})
 view=AccessControlFoundationView();role=Role.objects.filter(name='隔离测试本人开工员（不报工完工）').first()
 if role is None:
  value=view._save_role({'name':'隔离测试本人开工员（不报工完工）','description':reason},actor=user,reason=reason);role=Role.objects.get(pk=value['id']);view._set_role_permissions({'roleId':role.pk,'permissionCodes':[native.READ_PERMISSION,native.START_ACTION]},actor=user,reason=reason)
 if set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!={native.READ_PERMISSION,native.START_ACTION}:fail('TEST_START_ROLE_CONFLICT','专用角色范围发生冲突。')
 node=WorkflowNodeDefinition.objects.get(node_code=native.WORKFLOW_NODE,active=True,business_action_code='production.operation.start',process_definition__definition_code=native.PROCESS,process_definition__active=True)
 duty=Responsibility.objects.get(code=native.RESPONSIBILITY,status='ACTIVE',is_active=True);out=[]
 for tid in task_ids:
  task=ProductionWorkshopTask.objects.get(pk=tid,company_id=user.company_id,work_order__usage_purpose='TEST_BUSINESS');actor=User.objects.get(pk=task.assignment_snapshot['userId']);e,p,d,w,proof,valid=native._identity(actor)
  if not valid or not native._owned(actor,task,e) or p.pk!=task.execution_position_id:fail('TEST_START_ASSIGNEE_INVALID','真实派工本人任职不合法。')
  if not PositionResponsibility.objects.filter(position=p,responsibility=duty,active=True).exists():OrganizationOperatingService.execute(user=user,action='SAVE_POSITION_RESPONSIBILITY',request_identity=f'TEST-START-DUTY:{p.pk}:{duty.pk}',payload={'positionId':p.pk,'responsibilityId':duty.pk,'active':True,'isPrimary':False,'reason':reason})
  if not PositionWorkflowResponsibility.objects.filter(position=p,responsibility=duty,workflow_node=node,ownership_type='EXECUTOR',active=True).exists():OrganizationOperatingService.execute(user=user,action='SAVE_WORKFLOW_RESPONSIBILITY',payload={'positionId':p.pk,'responsibilityId':duty.pk,'workflowNodeId':node.pk,'ownershipType':'EXECUTOR','active':True,'reason':reason})
  old=list(UserRoleScopeAssignment.objects.filter(user=actor).order_by('id').values())
  value={'userId':actor.pk,'roleCode':role.code,'legalEntityId':str(user.company_id),'departmentId':None,'scopeCode':'ORGANIZATION','version':1}
  scope,created=UserRoleScopeAssignment.objects.get_or_create(user=actor,role=role,organization_id=user.company_id,defaults={'department':None,'scope_code':'ORGANIZATION','active':True,'version':1,'business_hash':business_hash(value)})
  if not scope.active or scope.scope_code!='ORGANIZATION' or scope.department_id is not None:fail('TEST_START_AUTHORITY_CONFLICT','已有专用授权不同，不能覆盖。')
  for original in old:
   if UserRoleScopeAssignment.objects.filter(pk=original['id']).values().get()!=original:fail('TEST_START_AUTHORITY_HISTORY_CHANGED','旧授权被改变。')
  if created:OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='APPEND_ISOLATED_TEST_START_AUTHORITY',target_type='UserRoleScopeAssignment',target_id=scope.pk,target_label=actor.username,reason=reason,before_snapshot={'preservedAuthorityIds':[x['id'] for x in old]},after_snapshot={**value,'employeeId':e.pk,'positionId':p.pk,'workshopId':w.pk,'testTaskId':task.pk,'selfFrozenTaskOnly':True,'permissionCodes':[native.READ_PERMISSION,native.START_ACTION],'formalAuthorityGranted':False})
  out.append({'taskId':task.pk,'actorId':actor.pk,'username':actor.username,'employeeName':e.full_name,'positionId':p.pk,'workshopId':w.pk,'authorityCreated':created})
 return {'source':'正常组织职责、角色维护及经管理员校验审计的非破坏性追加授权','assignees':out,'permissionCodes':[native.READ_PERMISSION,native.START_ACTION]}
