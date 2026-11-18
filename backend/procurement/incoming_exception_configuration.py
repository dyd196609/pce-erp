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
 for kind,code in CODES.items():
  label,domain,duty,roles=SPECS[kind]
  row,created=Permission.objects.get_or_create(code=code,defaults={'name':label,'module':domain})
  if row.name!=label or row.module!=domain:fail('INCOMING_EXCEPTION_PERMISSION_CONFLICT','既有同码权限含义不同，不能覆盖。')
  if created:
   audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='REGISTER_INCOMING_EXCEPTION_PERMISSION',target_type='Permission',target_id=row.pk,target_label=label,reason=reason,after_snapshot={'configurationOnly':True,'permissionCode':code,'requestIdentity':request_identity})
   changes.append({'permission':code,'auditId':audit.pk})
 definition={'definitionCode':PROCESS,'definitionName':'来料不合格登记与实物保管责任','businessDomain':'SCM','documentType':'IncomingQualityExceptionFact','version':1,'active':True,'description':'两个事实登记节点，不审批、不处置、不结案、不记库存。'}
 nodes=[{'nodeCode':kind.upper(),'nodeName':SPECS[kind][0],'sequence':n,'businessActionCode':code,'active':True,'description':'原职责范围内显式追加事实，历史保留，禁止金融或库存执行。'} for n,(kind,code) in enumerate(CODES.items(),1)]
 definitions=_definition(user,definition,nodes,reason,request_identity+'-definition')
 employees=list(formal_employee_queryset(company_id=user.company_id).select_related('position_ref','user'))
 for kind,code in CODES.items():
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
