"""Two approved facts-only actions, original roles/responsibilities and scopes."""
from django.db import transaction
from system.models import Permission,Role,RolePermission,UserRoleScopeAssignment,PositionResponsibility,OrganizationOperatingAuditRecord
from pfm.formal_employee import formal_employee_queryset
from planning.operation_handover_configuration import admin,foundation,_definition,_assign_existing_node,fail
from .incoming_exception_service import CODES,PROCESS
SPECS={'register':('来料不合格异常登记','QMS','RESP_QA_EXCEPTION_003',{'quality_inspector'}),
 'custody':('来料不合格实物保管核对','WMS','RESP_WH_IO_001',{'warehouse'})}
@transaction.atomic
def configure(*,user,reason,request_identity):
 admin(user)
 if not reason or not request_identity:fail('INCOMING_EXCEPTION_CONFIG_REASON_REQUIRED','须本次批准依据和配置同次标识。',400)
 changes=[];links=[]
 for kind in SPECS:
  code=CODES[kind]
  label,domain,duty,roles=SPECS[kind]
  row,created=Permission.objects.get_or_create(code=code,defaults={'name':label,'module':domain})
  if row.name!=label or row.module!=domain:fail('INCOMING_EXCEPTION_PERMISSION_CONFLICT','既有同码权限含义不同，不能覆盖。')
  if created:
   audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='REGISTER_INCOMING_EXCEPTION_PERMISSION',target_type='Permission',target_id=row.pk,target_label=label,reason=reason,after_snapshot={'configurationOnly':True,'permissionCode':code,'requestIdentity':request_identity})
   changes.append({'permission':code,'auditId':audit.pk})
 definition={'definitionCode':PROCESS,'definitionName':'来料不合格登记与实物保管责任','businessDomain':'SCM','documentType':'IncomingQualityExceptionFact','version':1,'active':True,'description':'两个事实登记节点，不审批、不处置、不结案、不记库存。'}
 nodes=[{'nodeCode':kind.upper(),'nodeName':SPECS[kind][0],'sequence':n,'businessActionCode':code,'active':True,'description':'原职责范围内显式追加事实，历史保留，禁止金融或库存执行。'} for n,(kind,code) in enumerate([(k,CODES[k]) for k in SPECS],1)]
 from workflow_runtime.models import ProcessDefinition
 existing=ProcessDefinition.objects.filter(definition_code=PROCESS).first()
 if existing and existing.nodes.filter(node_code='OPINION').exists():nodes.append(OPINION_NODE)
 definitions=_definition(user,definition,nodes,reason,request_identity+'-definition')
 employees=list(formal_employee_queryset(company_id=user.company_id).select_related('position_ref','user'))
 for kind in SPECS:
  code=CODES[kind]
  label,domain,duty,roles=SPECS[kind]
  for role in Role.objects.filter(code__in=roles):
   if UserRoleScopeAssignment.objects.filter(role=role,active=True).exclude(organization_id=user.company_id).exists():fail('INCOMING_EXCEPTION_SHARED_ROLE_PENDING','角色跨企业复用，需窄化方案，不能扩大组织范围。')
   ids=set(UserRoleScopeAssignment.objects.filter(role=role,organization_id=user.company_id,active=True).values_list('user_id',flat=True))
   selected=[e for e in employees if e.user_id in ids and PositionResponsibility.objects.filter(position_id=e.position_ref_id,active=True,responsibility__code=duty,responsibility__is_active=True,responsibility__status='ACTIVE').exists()]
   if not selected:continue
   old=set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))
   if code not in old:
    result=foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':sorted(old|{code}),'appendOnly':True,'expectedPermissionCodes':sorted(old)},reason)
    changes.append({'role':role.code,'addedPermission':code,'maintenance':result})
   for position in sorted({e.position_ref_id for e in selected}):
    e=next(x for x in selected if x.position_ref_id==position)
    links.append(_assign_existing_node(user,e,PROCESS,kind.upper(),duty,'EXECUTOR',reason,request_identity+'-'+kind+'-'+str(position)))
 return {'configurationOnly':True,'changes':changes,'workflowDefinitions':definitions,'workflowResponsibilityIds':links,'newAccountsRolesPeopleScopes':0,'dailyBusinessActions':0}


OPINION_NODE={'nodeCode':'OPINION','nodeName':'来料异常供应商意见记录','sequence':3,'businessActionCode':'procurement.incoming_exception.opinion','active':True,'description':'负责采购员本人追加供应商回复；不决定退供、不记库存、不结案。'}

@transaction.atomic
def configure_opinion(*,user,employee_id,scope_authority_id,reason,request_identity):
 """One explicitly approved narrow role/person grant, cloned from an exact prior scope."""
 from system.models import Responsibility
 from workflow_runtime.models import ProcessDefinition
 from workflow_runtime.definition_service import WorkflowDefinitionOperatingService
 from system.models import Company
 admin(user)
 if not reason or not request_identity:fail('INCOMING_EXCEPTION_CONFIG_REASON_REQUIRED','须本次批准依据及配置同次标识。',400)
 employee=formal_employee_queryset(company_id=user.company_id).filter(pk=employee_id).select_related('user','position_ref','department_ref').first()
 if not employee or not PositionResponsibility.objects.filter(position=employee.position_ref,active=True,responsibility__code='RESP_PUR_EXCEPTION_004',responsibility__is_active=True,responsibility__status='ACTIVE').exists():fail('INCOMING_EXCEPTION_ORIGINAL_DUTY_REQUIRED','明确人员须已有原有效采购异常协调职责。')
 old=UserRoleScopeAssignment.objects.filter(pk=scope_authority_id,user_id=employee.user_id,organization_id=user.company_id,active=True,scope_code='ORGANIZATION',department__isnull=True).first()
 if not old:fail('INCOMING_EXCEPTION_ORIGINAL_SCOPE_REQUIRED','须明确既有COMP001组织范围证据，不新授ALL或扩大范围。')
 code=CODES['opinion'];permission,created=Permission.objects.get_or_create(code=code,defaults={'name':'来料异常供应商意见记录','module':'SCM'})
 if permission.name!='来料异常供应商意见记录' or permission.module!='SCM':fail('INCOMING_EXCEPTION_PERMISSION_CONFLICT','既有同码权限含义不同。')
 audit_id=None
 if created:
  audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='REGISTER_INCOMING_EXCEPTION_PERMISSION',target_type='Permission',target_id=permission.pk,target_label=permission.name,reason=reason,after_snapshot={'permissionCode':code,'configurationOnly':True,'requestIdentity':request_identity})
  audit_id=audit.pk
 definition=ProcessDefinition.objects.filter(definition_code=PROCESS,active=True).first()
 if not definition:fail('INCOMING_EXCEPTION_ORIGINAL_WORKFLOW_REQUIRED','先复用已加载的异常登记与保管流程，不重复创建。')
 node=definition.nodes.filter(node_code='OPINION').first();node_result=None
 if node:
  if any(getattr(node,f)!=OPINION_NODE[k] for k,f in [('nodeName','node_name'),('sequence','sequence'),('businessActionCode','business_action_code'),('active','active'),('description','description')]):fail('INCOMING_EXCEPTION_NODE_CONFLICT','既有意见节点含义不同，不覆盖。')
 else:node_result=WorkflowDefinitionOperatingService.execute(user=user,action='SAVE_WORKFLOW_NODE',payload={**OPINION_NODE,'processDefinitionId':definition.pk,'reason':reason})
 name=Company.objects.get(pk=user.company_id).code+' 来料异常供应商意见记录'
 description='来料异常正式负责采购员本人追加供应商回复；仅单权限与已批准原范围，不授处置或其他采购资格。'
 role=Role.objects.filter(name=name).first()
 if role is None:
  created_role=foundation(user,'SAVE_ROLE',{'name':name,'description':description},reason)
  role=Role.objects.get(pk=created_role['id'])
  foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':[code]},reason)
 elif role.description!=description or set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!={code}:
  fail('INCOMING_EXCEPTION_NARROW_ROLE_CONFLICT','既有同名角色权限或用途不同，不覆盖。')
 existing=UserRoleScopeAssignment.objects.filter(user_id=employee.user_id,role=role,organization_id=user.company_id,active=True,scope_code=old.scope_code,department_id=old.department_id).first()
 grant=None
 if not existing:
  grant=foundation(user,'SET_USER_AUTHORITIES',{'userId':employee.user_id,'appendOnly':True,'authorities':[{'roleCode':role.code,'legalEntityId':str(user.company_id),'departmentId':old.department_id,'scopeCode':old.scope_code}]},reason)
 assigned=_assign_existing_node(user,employee,PROCESS,'OPINION','RESP_PUR_EXCEPTION_004','EXECUTOR',reason,request_identity+'-opinion')
 return {'configurationOnly':True,'permissionCreated':created,'permissionCode':code,'permissionAuditId':audit_id,'roleId':role.pk,'roleCode':role.code,'roleName':role.name,'employeeId':employee.pk,'employeeNo':employee.employee_no,'organizationId':user.company_id,'originalScopeAuthorityId':old.pk,'nodeResult':node_result,'scopeGrant':grant,'workflowResponsibilityId':assigned,'dailyBusinessActions':0}
