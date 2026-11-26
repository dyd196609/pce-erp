"""Approved two execution nodes; reuse existing roles, people and their scope."""
from django.db import transaction
from system.models import Role,RolePermission,UserRoleScopeAssignment,PositionResponsibility,PositionWorkflowResponsibility
from pfm.formal_employee import formal_employee_queryset
from planning.operation_handover_configuration import admin,foundation,_definition,_assign_existing_node,fail
ISSUE='warehouse.material.issue'
RECEIVE='production.material.receive'
SPECS={ISSUE:('WMS_PRODUCTION_MATERIAL_ISSUE','CONFIRM_PRODUCTION_MATERIAL_ISSUE','RESP_WH_IO_001','生产用料实际发料','WMS'),
 RECEIVE:('WMS_PRODUCTION_MATERIAL_ISSUE','CONFIRM_PRODUCTION_MATERIAL_RECEIPT','RESP_PROD_PLAN_001','生产用料领用收讫','MES')}

@transaction.atomic
def configure(*,user,reason,request_identity):
 admin(user)
 if not reason or not request_identity:fail('MATERIAL_ISSUE_CONFIG_REASON_REQUIRED','配置须有明确批准依据和同次标识。',400)
 changes=[];links=[];definitions=[]
 definition={'definitionCode':SPECS[ISSUE][0],'definitionName':'生产用料实际发料与车间收讫','businessDomain':'WMS','documentType':'ProductionMaterialIssue','version':1,'active':True,'description':'用户批准的同一原料交付流程，两项执行确认，不增加审批层级、角色或范围。'}
 nodes=[{'nodeCode':SPECS[code][1],'nodeName':SPECS[code][3],'sequence':index,'businessActionCode':code,'active':True,'description':'实际发出扣库一次；指定人收讫不再扣库，差异保持待核。'} for index,code in enumerate([ISSUE,RECEIVE],1)]
 definitions+=_definition(user,definition,nodes,reason,request_identity+'-delivery')
 employees=list(formal_employee_queryset(company_id=user.company_id).select_related('position_ref','user'))
 for code,(process,node,duty,label,domain) in SPECS.items():
  if code==ISSUE:
   role_ids=set(Role.objects.filter(code='warehouse').values_list('pk',flat=True))
   ids=set(UserRoleScopeAssignment.objects.filter(role_id__in=role_ids,organization_id=user.company_id,active=True).values_list('user_id',flat=True))
   selected=[e for e in employees if e.user_id in ids and PositionResponsibility.objects.filter(position_id=e.position_ref_id,active=True,responsibility__code=duty,responsibility__is_active=True,responsibility__status='ACTIVE').exists()]
  else:
   old_positions=set(PositionWorkflowResponsibility.objects.filter(active=True,ownership_type='OWNER',position__company_id=user.company_id,workflow_node__active=True,workflow_node__business_action_code='production.order.receive',responsibility__code=duty,responsibility__status='ACTIVE',responsibility__is_active=True).values_list('position_id',flat=True))
   selected=[e for e in employees if e.position_ref_id in old_positions and e.position_ref.workshop_id and PositionResponsibility.objects.filter(position_id=e.position_ref_id,active=True,responsibility__code=duty,responsibility__is_active=True).exists()]
   role_ids=set(UserRoleScopeAssignment.objects.filter(user_id__in=[e.user_id for e in selected],organization_id=user.company_id,active=True,role__rolepermission__permission__code='production.order.receive').values_list('role_id',flat=True))
  if not selected or not role_ids:fail('MATERIAL_ISSUE_CONFIG_EXISTING_ACTORS_REQUIRED','原有效仓管/车间接单人员及原角色尚未齐备，不自动补人或扩权。')
  for role in Role.objects.filter(pk__in=role_ids):
   if UserRoleScopeAssignment.objects.filter(role=role,active=True).exclude(organization_id=user.company_id).exists():fail('MATERIAL_ISSUE_SHARED_ROLE_SCOPE_PENDING','该角色跨组织复用，不能将本次配置扩及其他组织。')
   old=set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))
   if code not in old:
    result=foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':sorted(old|{code}),'appendOnly':True,'expectedPermissionCodes':sorted(old)},reason)
    changes.append({'role':role.code,'added':[code],'maintenance':result})
  seen=set()
  for e in selected:
   if e.position_ref_id in seen:continue
   seen.add(e.position_ref_id);links.append(_assign_existing_node(user,e,process,node,duty,'EXECUTOR',reason,request_identity+'-'+code+'-'+str(e.position_ref_id)))
 return {'configurationOnly':True,'roleChanges':changes,'definitionResults':definitions,'workflowResponsibilityIds':links,'newPeopleAccountsRolesScopes':0,'dailyBusinessActions':0}
