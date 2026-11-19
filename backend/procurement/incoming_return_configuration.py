"""Explicitly approved configuration only; never grant during import or read."""
from django.db import transaction
from system.models import Permission,Role,RolePermission,UserRoleScopeAssignment,PositionResponsibility,Responsibility,Company,OrganizationOperatingAuditRecord
from pfm.formal_employee import formal_employee_queryset
from planning.operation_handover_configuration import admin,foundation,org,_definition,_assign_existing_node,business_today
from .material_stock_authority import fail
from .incoming_return_service import CODES,DUTIES,NODES,PROCESS,WORKFLOW_DOCUMENT

NAMES={'return_request':'来料不合格退供申请','return_decide':'来料不合格企业退供决定','return_handover':'来料不合格现场签收交付'}
DUTY_NAME='来料不合格企业退供决定'
DUTY_DESCRIPTION='采购经理在原有效范围对准确未合格入账异常的退供申请作一个环节企业决定；与申请人、意见经办人及实交人分离；不授库存、结算或异常结案。'

@transaction.atomic
def configure(*,user,requester_employee_id,scope_authority_id,reason,request_identity):
 admin(user)
 if not reason or not request_identity:fail('INCOMING_RETURN_CONFIG_REASON_REQUIRED','须明确本次批准依据及维护意图。',400)
 employees=list(formal_employee_queryset(company_id=user.company_id).select_related('user','position_ref','department_ref'))
 applicant=next((e for e in employees if e.pk==requester_employee_id),None)
 if not applicant or not applicant.user_id or not PositionResponsibility.objects.filter(position_id=applicant.position_ref_id,active=True,
    responsibility__code=DUTIES['return_request'],responsibility__status='ACTIVE',responsibility__is_active=True).exists():
  fail('INCOMING_RETURN_CONFIG_APPLICANT_UNPROVEN','复用人员须已有原采购异常协调职责，不新建人员或岗位。')
 original=UserRoleScopeAssignment.objects.filter(pk=scope_authority_id,user_id=applicant.user_id,organization_id=user.company_id,active=True).exclude(scope_code='ALL').first()
 if not original:fail('INCOMING_RETURN_CONFIG_SCOPE_UNPROVEN','须明确原有效组织或部门或本人授权依据，不扩大范围。')
 changes=[];links=[]
 for kind,code in CODES.items():
  module='WMS' if kind=='return_handover' else 'SCM'
  p,created=Permission.objects.get_or_create(code=code,defaults={'name':NAMES[kind],'module':module})
  if p.name!=NAMES[kind] or p.module!=module:fail('INCOMING_RETURN_PERMISSION_CONFLICT','既有同码权限含义不同，不覆盖。')
  if created:
   audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='REGISTER_INCOMING_RETURN_PERMISSION',
    target_type='Permission',target_id=p.pk,target_label=p.name,reason=reason,after_snapshot={'permissionCode':code,'configurationOnly':True,'requestIdentity':request_identity})
   changes.append({'permission':code,'auditId':audit.pk})
 duty=Responsibility.objects.filter(code=DUTIES['return_decide']).first()
 if duty is None:
  payload={'code':DUTIES['return_decide'],'name':DUTY_NAME,'description':DUTY_DESCRIPTION,
    'businessDomain':'SCM','status':'DRAFT','effectiveFrom':business_today().isoformat(),'effectiveTo':None}
  created=org(user,'SAVE_RESPONSIBILITY',payload,reason,request_identity+'-duty-draft');changes.append(created)
  duty=Responsibility.objects.get(code=DUTIES['return_decide'])
  changes.append(org(user,'SAVE_RESPONSIBILITY',{**payload,'id':duty.pk,'status':'ACTIVE'},reason,request_identity+'-duty-active'))

 elif duty.name!=DUTY_NAME or duty.description!=DUTY_DESCRIPTION or duty.status!='ACTIVE' or not duty.is_active:
  fail('INCOMING_RETURN_DUTY_CONFLICT','既有企业退供决定职责不同或停用，不能覆盖恢复。')
 definition={'definitionCode':PROCESS,'definitionName':'未合格入账来料退供','businessDomain':'SCM','documentType':WORKFLOW_DOCUMENT,
  'version':1,'active':True,'description':'负责采购员申请、采购经理一个环节决定、原仓管现场签收交付；无库存或结算效力。'}
 nodes=[{'nodeCode':NODES[kind],'nodeName':NAMES[kind],'sequence':n,'businessActionCode':code,'active':True,
  'description':'原范围显式办理，准确来源版本及同次结果；仅经理为一个审批环节，不产生IN/OUT或结案。'} for n,(kind,code) in enumerate(CODES.items(),1)]
 definitions=_definition(user,definition,nodes,reason,request_identity+'-workflow')
 name=Company.objects.get(pk=user.company_id).code+' 来料不合格退供申请'
 description='仅正式负责采购员在原范围申请未合格入账来料退供；单权限，不含企业决定、交付、其他采购或金融资格。'
 role=Role.objects.filter(name=name).first()
 if role is None:
  result=foundation(user,'SAVE_ROLE',{'name':name,'description':description},reason);role=Role.objects.get(pk=result['id'])
  changes.append({'requestRoleCreated':result})
  changes.append(foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':[CODES['return_request']]},reason))
 elif role.description!=description or set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!={CODES['return_request']}:
  fail('INCOMING_RETURN_REQUEST_ROLE_CONFLICT','既有同名角色不是本单权限用途，不覆盖。')
 grant=UserRoleScopeAssignment.objects.filter(user_id=applicant.user_id,role=role,organization_id=user.company_id,active=True,
  scope_code=original.scope_code,department_id=original.department_id).first()
 if grant is None:
  changes.append(foundation(user,'SET_USER_AUTHORITIES',{'userId':applicant.user_id,'appendOnly':True,'authorities':[{
   'roleCode':role.code,'legalEntityId':str(user.company_id),'departmentId':original.department_id,'scopeCode':original.scope_code}]},reason))
 links.append(_assign_existing_node(user,applicant,PROCESS,NODES['return_request'],DUTIES['return_request'],'EXECUTOR',reason,request_identity+'-request'))
 for kind,role_code in [('return_decide','purchase_manager'),('return_handover','warehouse')]:
  existing=Role.objects.filter(code=role_code).first()
  if not existing:fail('INCOMING_RETURN_ORIGINAL_ROLE_REQUIRED','须复用既有采购经理和仓管角色，不新增替代岗位。')
  assignments=UserRoleScopeAssignment.objects.filter(role=existing,active=True)
  if assignments.exclude(organization_id=user.company_id).exists() or assignments.filter(scope_code='ALL').exists():
   fail('INCOMING_RETURN_SHARED_ROLE_SCOPE_PENDING','原角色跨企业或ALL范围未获本次授权，先保留待核，不能扩授。')
  ids=set(assignments.filter(organization_id=user.company_id).values_list('user_id',flat=True))
  selected=[e for e in employees if e.user_id in ids]
  if kind=='return_handover':
   selected=[e for e in selected if PositionResponsibility.objects.filter(position_id=e.position_ref_id,active=True,
     responsibility__code=DUTIES[kind],responsibility__status='ACTIVE',responsibility__is_active=True).exists()]
  if not selected:fail('INCOMING_RETURN_CONFIG_ORIGINAL_PARTICIPANT_REQUIRED','原角色未具有效人员和职责依据，不临时补人。')
  codes=set(RolePermission.objects.filter(role=existing).values_list('permission__code',flat=True))
  if CODES[kind] not in codes:
   changes.append(foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':existing.pk,'permissionCodes':sorted(codes|{CODES[kind]}),
    'appendOnly':True,'expectedPermissionCodes':sorted(codes)},reason))
  for position in sorted({e.position_ref_id for e in selected}):
   employee=next(e for e in selected if e.position_ref_id==position)
   links.append(_assign_existing_node(user,employee,PROCESS,NODES[kind],DUTIES[kind],
    'OWNER' if kind=='return_decide' else 'EXECUTOR',reason,request_identity+'-'+kind+'-'+str(position)))
 return {'configurationOnly':True,'changes':changes,'workflowDefinitions':definitions,'workflowResponsibilityIds':links,
  'requestRoleId':role.pk,'requestRoleCode':role.code,'requesterEmployeeId':applicant.pk,'originalScopeAuthorityId':original.pk,
  'newPermissions':list(CODES.values()),'dailyBusinessActions':0,'newPeopleAccountsPositionsOrOrganizations':0,'approvalStages':1}
