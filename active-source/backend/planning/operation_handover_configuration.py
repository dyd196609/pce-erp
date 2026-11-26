"""Explicit catalogue and participant maintenance, never import-time granting.

Participants are caller-selected existing accounts and exact WC scopes. The
same services are usable by a controlled maintenance command and isolation
verification; no seed fabricates qualification or approval decisions.
"""
from types import SimpleNamespace
from django.db import transaction
from django.utils import timezone
from pfm.formal_employee import formal_employee_queryset
from system.models import (Permission,Responsibility,PositionResponsibility,PositionWorkflowResponsibility,
    Role,RolePermission,UserRoleScopeAssignment,OrganizationOperatingAuditRecord,Company,User)
from system.organization_operating import OrganizationOperatingService
from system.authorization import AuthorizationService
from system.access_control_views import AccessControlFoundationView,business_hash
from workflow_runtime.models import ProcessDefinition
from workflow_runtime.definition_service import WorkflowDefinitionOperatingService,serialize_definition
from .operation_handover_contract import ACTIONS as HANDOVER_ACTIONS
from .operation_output_contract import ACTIONS as OUTPUT_ACTIONS
from .operation_handover_permissions import PROCESS,NODES,DEFINITION,NODE_SPECS,NODE_LABELS
from .services import PlanningBusinessError

def fail(code,message,status=409):raise PlanningBusinessError(code,message,http_status=status)
def business_today():
    now=timezone.now()
    return timezone.localdate(now) if timezone.is_aware(now) else now.date()
def admin(user):
    q=AuthorizationService.decide(user=user,action_code='system.organization.workflow_responsibility.manage',organization_id=user.company_id)
    if not q['allowed'] or not user.is_superuser:fail('HANDOVER_CONFIG_ADMIN_REQUIRED','须由正式授权管理员明确维护目录及责任。',403)
    return q

def org(user,action,payload,reason,identity):
    return OrganizationOperatingService.execute(user=user,action=action,payload={**payload,'reason':reason},request_identity=identity)

def foundation(user,action,payload,reason):
    response=AccessControlFoundationView().post(SimpleNamespace(user=user,data={'action':action,
        'payload':{**payload,'reason':reason,'expectedActorId':user.pk}}))
    if response.status_code!=200 or not response.data.get('success'):
        error=response.data.get('error') or {}
        fail(error.get('code','HANDOVER_CONFIG_FAILED'),error.get('message','正式权限维护失败。'),response.status_code)
    return response.data['data']['result']

def _definition(user,definition,nodes,reason,key):
    row=ProcessDefinition.objects.filter(definition_code=definition['definitionCode']).first()
    results=[]
    if row:
        current=serialize_definition(row)
        if any(current[k]!=v for k,v in definition.items()):fail('HANDOVER_DEFINITION_CONFLICT','既有同码模板语义不同，禁止覆盖。')
    else:
        results.append(WorkflowDefinitionOperatingService.configure_atomic_minimal_template(user=user,
            payload={'definition':definition,'node':nodes[0],'reason':reason},idempotency_key=key+'-definition'))
        row=ProcessDefinition.objects.get(definition_code=definition['definitionCode'])
    if row.nodes.exclude(node_code__in=[n['nodeCode'] for n in nodes]).exists():fail('HANDOVER_DEFINITION_NODE_CONFLICT','同码模板有额外节点，不能覆盖。')
    for spec in nodes:
        node=row.nodes.filter(node_code=spec['nodeCode']).first()
        if not node:
            results.append(WorkflowDefinitionOperatingService.execute(user=user,action='SAVE_WORKFLOW_NODE',
                payload={**spec,'processDefinitionId':row.pk,'reason':reason}))
        elif any(getattr(node,field)!=spec[k] for k,field in [('nodeName','node_name'),('sequence','sequence'),
                ('businessActionCode','business_action_code'),('active','active'),('description','description')]):
            fail('HANDOVER_DEFINITION_NODE_CONFLICT','既有同码节点语义不同，禁止覆盖。')
    return results

@transaction.atomic
def register_handover_configuration(*,user,reason,request_identity):
    admin(user)
    if not reason or len(reason.strip())<2 or not request_identity:fail('HANDOVER_CONFIG_REASON_REQUIRED','目录登记须有真实原因及请求身份。',400)
    original={r.pk:r.definition_hash for r in ProcessDefinition.objects.all()}
    from .operation_completion_v3_authority import DEFINITION as V3_DEFINITION,NODES as V3_NODES,WITHDRAW_ACTION
    catalog={code:label for code,label in list(HANDOVER_ACTIONS.values())+list(OUTPUT_ACTIONS.values())}
    catalog.update({n['businessActionCode']:n['nodeName'] for n in V3_NODES})
    created=[]
    for code,label in catalog.items():
        old=Permission.objects.filter(code=code).first()
        if old:
            if old.module!='MES':fail('HANDOVER_PERMISSION_CONFLICT','既有同码权限所属模块不同。')
            continue
        row=Permission.objects.create(code=code,name=label,module='MES')
        audit=WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_OPERATION_HANDOVER_PERMISSION',target=row,
            target_type='Permission',label=label,reason=reason,before={},after={'permissionCode':code,'configurationOnly':True,'requestIdentity':request_identity})
        created.append({'permissionId':row.pk,'auditId':audit.pk,'code':code})
    definition=dict(DEFINITION);labels=dict(NODE_LABELS);nodes=[dict(n) for n in NODE_SPECS]
    result=_definition(user,definition,nodes,reason,request_identity+'-handover')
    result+=_definition(user,dict(V3_DEFINITION),[dict(n) for n in V3_NODES],reason,request_identity+'-v3')
    for pk,oldhash in original.items():
        if ProcessDefinition.objects.get(pk=pk).definition_hash!=oldhash:fail('HANDOVER_LEGACY_TEMPLATE_CHANGED','目录登记改变既有模板Hash，事务回滚。')
    duties=[]
    today=business_today().isoformat()
    for kind,(node_code,code) in NODES.items():
        row=Responsibility.objects.filter(code=code).first()
        fields={'code':code,'name':labels[kind],'description':'正式工序交接职责，仅在明确WC绑定和人员授权后生效。','businessDomain':'MES','effectiveFrom':today}
        if row is None:
            draft=org(user,'SAVE_RESPONSIBILITY',{**fields,'status':'DRAFT'},reason,request_identity+'-'+kind+'-draft')
            row=Responsibility.objects.get(pk=draft['target']['id'])
            org(user,'SAVE_RESPONSIBILITY',{**fields,'id':row.pk,'status':'ACTIVE'},reason,request_identity+'-'+kind+'-active')
        elif row.status!='ACTIVE' or not row.is_active:fail('HANDOVER_DUTY_INACTIVE','既有同码职责未生效，不静默恢复。')
        duties.append(row.pk)
    return {'configurationOnly':True,'permissionCreated':created,'workflowResults':result,'responsibilityIds':duties,
        'oldDefinitionHashesUnchanged':True,'humanAuthorizationWriteCount':0}

def _existing_person(company_id,account_id,position_id):
    rows=list(formal_employee_queryset(company_id=company_id).filter(user_id=account_id,position_ref_id=position_id).select_related('user','position_ref')[:2])
    if len(rows)!=1 or rows[0].user.is_superuser:fail('HANDOVER_CONFIG_PERSON_INVALID','必须明确唯一有效既有员工、账户及岗位。')
    return rows[0]

def _role(user,label,codes,reason):
    name=Company.objects.get(pk=user.company_id).code+' '+label
    description='工序交接正式职责授权；仅明确参与人及精确WC范围，不更改原角色。'
    role=Role.objects.filter(name=name).first()
    if not role:
        result=foundation(user,'SAVE_ROLE',{'name':name,'description':description},reason)
        role=Role.objects.get(pk=result['id'])
        foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':sorted(codes)},reason)
    elif role.description!=description or set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!=set(codes):
        fail('HANDOVER_CONFIG_ROLE_CONFLICT','既有同名角色权限不同，不覆盖。')
    return role

def _append_grant(user,employee,role,reason,identity):
    # Additive formal maintenance: retain all old authority IDs referenced by historical proofs.
    payload={'userId':employee.user_id,'roleCode':role.code,'legalEntityId':str(user.company_id),
        'departmentId':None,'scopeCode':'ORGANIZATION','version':1}
    row,created=UserRoleScopeAssignment.objects.get_or_create(user_id=employee.user_id,role=role,organization_id=user.company_id,
        defaults={'department':None,'scope_code':'ORGANIZATION','active':True,'version':1,'business_hash':business_hash(payload)})
    if not row.active or row.scope_code!='ORGANIZATION' or row.department_id is not None:fail('HANDOVER_CONFIG_SCOPE_CONFLICT','同角色原范围不同，不自动覆盖。')
    if created:
        OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='APPEND_OPERATION_HANDOVER_AUTHORITY',
            target_type='User',target_id=employee.user_id,target_label=employee.user.username,reason=reason,before_snapshot={'priorAuthoritiesPreserved':True},
            after_snapshot={'authority':payload,'authorityId':row.pk,'employeeId':employee.pk,'requestIdentity':identity,'configurationOnly':True})
    return row.pk

@transaction.atomic
def configure_handover_participant(*,user,account_id,position_id,work_center_id,kind,reason,request_identity):
    """Explicit one-person/WC responsibility choice through native governance services."""
    admin(user)
    if kind not in NODES:fail('HANDOVER_CONFIG_KIND_INVALID','责任类型须为来源、接收或独立确认。',400)
    employee=_existing_person(user.company_id,account_id,position_id)
    definition=ProcessDefinition.objects.get(definition_code=PROCESS)
    node_code,duty_code=NODES[kind]
    node=definition.nodes.get(node_code=node_code);duty=Responsibility.objects.get(code=duty_code,status='ACTIVE')
    if not PositionResponsibility.objects.filter(position_id=position_id,responsibility=duty,active=True).exists():
        org(user,'SAVE_POSITION_RESPONSIBILITY',{'positionId':position_id,'responsibilityId':duty.pk,'isPrimary':False,'active':True},reason,request_identity+'-duty')
    relation=PositionWorkflowResponsibility.objects.filter(position_id=position_id,workflow_node=node).first()
    if not relation:
        result=org(user,'SAVE_WORKFLOW_RESPONSIBILITY',{'positionId':position_id,'responsibilityId':duty.pk,
            'workflowNodeId':node.pk,'ownershipType':'OWNER','active':True,'effectiveFrom':business_today().isoformat()},reason,request_identity+'-node')
        relation=PositionWorkflowResponsibility.objects.get(pk=result['target']['id'])
    from pde.work_center_responsibility_service import execute_work_center_responsibility,hash_value,state
    from pde.work_center_responsibility_models import WorkCenterResponsibilityScope
    old=WorkCenterResponsibilityScope.objects.filter(company_id=user.company_id,work_center_id=work_center_id,workflow_responsibility=relation).first()
    if old and (old.status!='active' or old.employee_id!=employee.pk):fail('HANDOVER_CONFIG_WC_SCOPE_CONFLICT','原WC责任绑定不同，不代改既有负责人。')
    scope_result=None
    if not old:
        scope_result=execute_work_center_responsibility(user=user,action='create',payload={'workCenterId':work_center_id,
            'workflowResponsibilityId':relation.pk,'employeeId':employee.pk,'effectiveFrom':business_today().isoformat(),'effectiveTo':None,
            'expectedVersion':None,'expectedScopeHash':None,'reason':reason,'idempotencyKey':request_identity+'-wc'})
    reads={HANDOVER_ACTIONS['read'][0],OUTPUT_ACTIONS['read'][0]}
    if kind=='REVIEW':codes=reads|{OUTPUT_ACTIONS[k][0] for k in ('excess.review','correct')}|{HANDOVER_ACTIONS['exception.confirm'][0]};label='工序交接独立确认员'
    else:
        codes=reads|{OUTPUT_ACTIONS['confirm'][0]}|{HANDOVER_ACTIONS[k][0] for k in ('prepare','dispatch','cancel','forward','return','receive','exception.submit','input.confirm')}
        label='工序交接负责人'
    role=_role(user,label,codes,reason);authority=_append_grant(user,employee,role,reason,request_identity)
    return {'configurationOnly':True,'accountId':account_id,'employeeId':employee.pk,'positionId':position_id,
        'workCenterId':work_center_id,'kind':kind,'workflowResponsibilityId':relation.pk,'roleCode':role.code,'authorityId':authority,
        'workCenterScopeCreated':old is None,'scopeResult':scope_result[0] if scope_result else None}

def _assign_existing_node(user,employee,process,node_code,duty_code,ownership,reason,identity):
    """Explicit native maintenance; never mutate an existing conflicting mapping."""
    definition=ProcessDefinition.objects.get(definition_code=process,active=True)
    node=definition.nodes.get(node_code=node_code,active=True)
    duty=Responsibility.objects.get(code=duty_code,status='ACTIVE',is_active=True)
    position_id=employee.position_ref_id
    mapping=PositionResponsibility.objects.filter(position_id=position_id,responsibility=duty).first()
    if mapping and not mapping.active:fail('HANDOVER_CONFIG_DUTY_DISABLED','原岗位职责已停用，不静默恢复。')
    if not mapping:
        org(user,'SAVE_POSITION_RESPONSIBILITY',{'positionId':position_id,'responsibilityId':duty.pk,'isPrimary':False,'active':True},reason,identity+'-duty')
    relation=PositionWorkflowResponsibility.objects.filter(position_id=position_id,workflow_node=node).first()
    if relation and (not relation.active or relation.ownership_type!=ownership or relation.responsibility_id!=duty.pk):
        fail('HANDOVER_CONFIG_NODE_CONFLICT','原岗位节点职责不同，不覆盖。')
    if not relation:
        result=org(user,'SAVE_WORKFLOW_RESPONSIBILITY',{'positionId':position_id,'responsibilityId':duty.pk,
            'workflowNodeId':node.pk,'ownershipType':ownership,'active':True,'effectiveFrom':business_today().isoformat()},reason,identity+'-node')
        relation=PositionWorkflowResponsibility.objects.get(pk=result['target']['id'])
    return relation.pk

@transaction.atomic
def configure_output_reporter(*,user,account_id,position_id,reason,request_identity):
    """Formal own-task reporter and supplemental report grant; no WC owner inference."""
    admin(user);employee=_existing_person(user.company_id,account_id,position_id)
    from .operation_report_contract import PROCESS as RP,WORKFLOW_NODE,RESPONSIBILITY,REPORT_ACTION,READ_PERMISSION
    relation=_assign_existing_node(user,employee,RP,WORKFLOW_NODE,RESPONSIBILITY,'EXECUTOR',reason,request_identity)
    from .operation_report_authority import append_operation_report_authority
    exact_roles=[]
    for grant in UserRoleScopeAssignment.objects.filter(user_id=account_id,organization_id=user.company_id,active=True,
            scope_code='ORGANIZATION',department__isnull=True).select_related('role'):
        if set(RolePermission.objects.filter(role=grant.role).values_list('permission__code',flat=True))=={READ_PERMISSION,REPORT_ACTION}:
            exact_roles.append(grant.role)
    if len(exact_roles)>1:fail('HANDOVER_CONFIG_REPORT_ROLE_AMBIGUOUS','既有本人报工专用角色不唯一，请先正式核定，不增重复授权。')
    report_role=exact_roles[0] if exact_roles else _role(user,'本人任务报工员',{READ_PERMISSION,REPORT_ACTION},reason)
    old=append_operation_report_authority(user=user,account_id=account_id,role_id=report_role.pk,reason=reason,request_identity=request_identity+'-report')
    codes={HANDOVER_ACTIONS['read'][0],OUTPUT_ACTIONS['read'][0],OUTPUT_ACTIONS['excess.report'][0],REPORT_ACTION}
    supplemental=_role(user,'本人任务超计划补充报工员',codes,reason)
    authority=_append_grant(user,employee,supplemental,reason,request_identity+'-supplement')
    return {'configurationOnly':True,'accountId':account_id,'employeeId':employee.pk,
        'workflowResponsibilityId':relation,'reportAuthority':old,'supplementAuthorityId':authority}

@transaction.atomic
def configure_completion_v3_participant(*,user,account_id,position_id,kind,reason,request_identity):
    admin(user);employee=_existing_person(user.company_id,account_id,position_id)
    from .operation_completion_v3_authority import ACTION_SPECS,PROCESS as VP
    from .operation_completion_contract import READ_PERMISSION,REQUEST_ACTION,APPROVE_ACTION
    if kind not in ('REQUEST','REVIEW'):fail('HANDOVER_CONFIG_V3_KIND_INVALID','整体完工职责须为申请或独审。')
    keys=('request','withdrawReplace') if kind=='REQUEST' else ('approve',)
    opposite=APPROVE_ACTION if kind=='REQUEST' else REQUEST_ACTION
    if UserRoleScopeAssignment.objects.filter(user_id=account_id,organization_id=user.company_id,active=True,
            role__rolepermission__permission__code=opposite).exists():
        fail('HANDOVER_CONFIG_V3_SEPARATION','整体申请与独审不得由同一人兼任。')
    nodes=[];codes={READ_PERMISSION}
    for key in keys:
        code,permission,node,duty,ownership,_=ACTION_SPECS[key]
        nodes.append(_assign_existing_node(user,employee,VP,node,duty,ownership,reason,request_identity+'-'+key))
        codes.add(permission)
    reusable=[]
    if kind=='REVIEW':
        for grant in UserRoleScopeAssignment.objects.filter(user_id=account_id,organization_id=user.company_id,active=True).select_related('role'):
            actual=set(RolePermission.objects.filter(role=grant.role).values_list('permission__code',flat=True))
            if actual==codes and grant.scope_code=='ORGANIZATION' and grant.department_id is None:
                reusable.append(grant.role)
        if len(reusable)>1:fail('HANDOVER_CONFIG_REVIEW_ROLE_AMBIGUOUS','存在多个同权审核角色，请先通过正式权限维护明确唯一角色，不代选。')
    role=reusable[0] if reusable else _role(user,'整体完工V3申请员' if kind=='REQUEST' else '整体完工V3独审员',codes,reason)
    authority=_append_grant(user,employee,role,reason,request_identity)
    return {'configurationOnly':True,'accountId':account_id,'employeeId':employee.pk,'kind':kind,
        'workflowResponsibilityIds':nodes,'roleCode':role.code,'authorityId':authority}

@transaction.atomic
def disable_handover_configuration_authority(*,user,authority_id,expected_version,reason,request_identity):
    """Explicitly retire only a grant created by this feature, retaining its identity/history."""
    admin(user)
    if type(authority_id) is not int or type(expected_version) is not int or not 2<=len(reason.strip())<=300 or not request_identity:
        fail('HANDOVER_CONFIG_AUTHORITY_INTENT_INVALID','停用本功能授权须明确范围、版本、原因及请求。',400)
    row=UserRoleScopeAssignment.objects.select_for_update().select_related('role').filter(pk=authority_id,organization_id=user.company_id).first()
    if not row or row.role.description!='工序交接正式职责授权；仅明确参与人及精确WC范围，不更改原角色。':
        fail('HANDOVER_CONFIG_AUTHORITY_NOT_OWNED','仅允许维护本功能正式新增的授权，不能借此改变既有授权。',403)
    if not row.active or row.version!=expected_version:fail('HANDOVER_CONFIG_AUTHORITY_VERSION_CHANGED','授权已变化，请重新读取准确版本。')
    before={'id':row.pk,'userId':row.user_id,'roleCode':row.role.code,'version':row.version,'active':row.active,'businessHash':row.business_hash}
    row.active=False;row.version+=1
    row.business_hash=business_hash({'userId':row.user_id,'roleCode':row.role.code,'legalEntityId':str(row.organization_id),
        'departmentId':str(row.department_id) if row.department_id else None,'scopeCode':row.scope_code,'version':row.version})
    row.save(update_fields=['active','version','business_hash'])
    after={'id':row.pk,'userId':row.user_id,'roleCode':row.role.code,'version':row.version,'active':False,'businessHash':row.business_hash}
    audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code='DISABLE_OPERATION_HANDOVER_AUTHORITY',
        target_type='UserRoleScopeAssignment',target_id=row.pk,target_label=row.role.name,reason=reason.strip(),before_snapshot=before,
        after_snapshot={**after,'requestIdentity':request_identity,'configurationOnly':True})
    return {'configurationOnly':True,'authorityId':row.pk,'auditId':audit.pk,'before':before,'after':after,'historicalAuthoritiesPreserved':True}

@transaction.atomic
def configure_range_release_participant(*,user,account_id,position_id,work_center_id,reason,request_identity):
    """Append this one action to an explicitly maintained exact SOURCE owner.

    Existing roles/permissions/scopes are never replaced. An OWNER mapping is
    maintained in the normal organization/WC entrance before this explicit grant.
    """
    admin(user);employee=_existing_person(user.company_id,account_id,position_id)
    code='production.operation.handover.range.release'
    if not Permission.objects.filter(code=code,module='MES').exists():
        fail('HANDOVER_RANGE_ACTION_NOT_REGISTERED','请先通过正式目录登记范围释放动作。')
    role=_role(user,'工序交接范围释放负责人',{HANDOVER_ACTIONS['read'][0],OUTPUT_ACTIONS['read'][0],code},reason)
    authority=_append_grant(user,employee,role,reason,request_identity)
    from .operation_handover_permissions import check_action
    q=check_action(user=employee.user,action_code=code,work_center_id=work_center_id,
        object_type='WorkCenter',object_id=work_center_id,status='open')
    if not q['ready']:fail('HANDOVER_RANGE_SOURCE_SCOPE_REQUIRED','须先正式维护该员工准确来源WC及SOURCE节点负责人绑定：'+q['statusLabel'])
    return {'configurationOnly':True,'accountId':account_id,'employeeId':employee.pk,'workCenterId':work_center_id,
        'roleCode':role.code,'authorityId':authority,'exactSourceQualification':q,'existingAuthoritiesPreserved':True}
