"""One approved execution node on the original shared workflow catalogue."""
from django.db import transaction
from system.models import Role,RolePermission,UserRoleScopeAssignment,PositionResponsibility
from pfm.formal_employee import formal_employee_queryset
from planning.operation_handover_configuration import admin,foundation,_definition,_assign_existing_node,fail
PERMISSION='warehouse.material.prepare'
PROCESS='WMS_PRODUCTION_MATERIAL_PREPARATION'
NODE='CONFIRM_PRODUCTION_MATERIAL_PREPARATION'
DUTY='RESP_WH_IO_001'
DEFINITION={'definitionCode':PROCESS,'definitionName':'生产用料原库位实物备料确认','businessDomain':'WMS',
 'documentType':'ProductionMaterialPreparation','version':1,'active':True,
 'description':'原有效占用内本人清点分拣标识摆妥后显式确认；不移位、不出库、不领料，不增加审批层级。'}
NODES=[{'nodeCode':NODE,'nodeName':'确认生产用料实物备料','sequence':1,'businessActionCode':PERMISSION,
 'active':True,'description':'原仓管在原库位内追加实物备料事实；原库存与占用保持。'}]

@transaction.atomic
def configure(*,user,reason,request_identity):
 admin(user)
 if not reason or not request_identity:fail('MATERIAL_CONFIG_REASON_REQUIRED','维护须有明确依据及同次标识。',400)
 role=Role.objects.get(code='warehouse')
 previous=set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True));changes=[]
 if PERMISSION not in previous:
  result=foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':sorted(previous|{PERMISSION}),'appendOnly':True,'expectedPermissionCodes':sorted(previous)},reason)
  changes.append({'role':role.code,'added':[PERMISSION],'maintenance':result})
 _definition(user,DEFINITION,NODES,reason,request_identity+'-definition')
 accounts=UserRoleScopeAssignment.objects.filter(role=role,organization_id=user.company_id,active=True).values('user_id')
 employees=formal_employee_queryset(company_id=user.company_id).filter(user_id__in=accounts).select_related('position_ref','user')
 positions=set();links=[]
 for e in employees:
  if e.position_ref_id in positions:continue
  if not PositionResponsibility.objects.filter(position=e.position_ref,active=True,responsibility__code=DUTY,responsibility__is_active=True,responsibility__status='ACTIVE').exists():
   fail('MATERIAL_CONFIG_EXISTING_DUTY_REQUIRED','只承接现有有效仓库出入库职责。')
  positions.add(e.position_ref_id)
  links.append(_assign_existing_node(user,e,PROCESS,NODE,DUTY,'EXECUTOR',reason,request_identity+'-position-'+str(e.position_ref_id)))
 if not positions:fail('MATERIAL_CONFIG_NO_EXISTING_WAREHOUSE_ACTOR','没有原在职仓管及有效职责。')
 return {'configurationOnly':True,'roleChanges':changes,'workflowResponsibilityIds':links,'newPeopleAccountsRolesScopes':0,'dailyBusinessActions':0}
