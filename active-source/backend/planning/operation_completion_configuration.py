"""Explicit, additive configuration for applicant/expeditor completion review.

No import-time writes; no business application, approval or completion is made.
The existing organization/workflow maintenance guards and audit services remain
the authority for maintenance. Existing roles and scope rows are never replaced.
"""
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from pfm.formal_employee import formal_employee_queryset
from system.access_control_views import AccessControlFoundationView, business_hash
from system.models import (Company, OrganizationOperatingAuditRecord, Permission, PositionResponsibility,
    PositionWorkflowResponsibility, Responsibility, Role, RolePermission, User, UserRoleScopeAssignment)
from system.organization_operating import OrganizationOperatingService
from workflow_runtime.definition_service import (WorkflowDefinitionCatalogService, WorkflowDefinitionOperatingService,
    WorkflowDefinitionError, serialize_definition)
from workflow_runtime.models import BusinessStateTransition, ProcessDefinition, WorkflowInstance, WorkflowNodeDefinition
from .mes_test_source_bridge import _assert_hash
from .mes_test_source_bridge import _effective
from .operation_completion_contract import (CONTRACT, OBJECT, PROCESS, BUSINESS_PROCESS, READ_PERMISSION,
    REQUEST_ACTION, APPROVE_ACTION, REQUEST_NODE, REVIEW_NODE, REQUEST_RESPONSIBILITY, REVIEW_RESPONSIBILITY)

PERMISSIONS = (
    {'code': READ_PERMISSION, 'name': '工序完工申请与审核查看', 'module': 'MES'},
    {'code': REQUEST_ACTION, 'name': '本人已报齐工序完工申请', 'module': 'MES'},
    {'code': APPROVE_ACTION, 'name': '生产跟单员工序完工审核确认', 'module': 'MES'},
)
DEFINITION = {'definitionCode': PROCESS, 'definitionName': '工序完工审核模板', 'businessDomain': 'MES',
    'documentType': OBJECT, 'version': 1, 'active': True,
    'description': '既有生产流程工序完工节点内部审批模板；申请不等于完工，生产跟单员审核后生效；不放行后序或转移。'}
NODES = (
    {'nodeCode': REQUEST_NODE, 'nodeName': '工序完工申请节点', 'sequence': 1, 'businessActionCode': REQUEST_ACTION,
     'active': True, 'description': '冻结执行人及实际开工报工人本人申请完工；申请只进入待审核，不形成生效完工。'},
    {'nodeCode': REVIEW_NODE, 'nodeName': '生产跟单员工序完工审核节点', 'sequence': 2, 'businessActionCode': APPROVE_ACTION,
     'active': True, 'description': '生产跟单员以不同账号及独立审核角色确认完工生效；不代申请，不转移、不放行后续。'},
)
DUTIES = (
    (REQUEST_RESPONSIBILITY, '本人已报齐工序完工申请', '冻结执行人本人核对已开工、正式报工和来源后提出完工申请；申请不代表已完工，不含审核或转移。', 'EXECUTOR'),
    (REVIEW_RESPONSIBILITY, '生产跟单员工序完工审核确认', '生产跟单员核对正式来源、开工、报工及申请事实，以不同账号和独立审核角色确认工序完工生效；不含转移或后序放行。', 'REVIEWER'),
)

def _fail(code, text):
    raise WorkflowDefinitionError(code, text, http_status=409)

def _request(reason, request_identity):
    reason, identity = str(reason or '').strip(), str(request_identity or '').strip()
    if not 2 <= len(reason) <= 300 or not 1 <= len(identity) <= 160:
        _fail('COMPLETION_CONFIGURATION_REQUEST_REQUIRED', '完工配置须有明确原因及不超过160字的唯一请求标识。')
    return reason, identity

def _admin(user):
    WorkflowDefinitionCatalogService.authorize(user)
    denied = AccessControlFoundationView()._admin_guard(SimpleNamespace(user=user))
    if denied is not None:
        error = denied.data['error']
        raise WorkflowDefinitionError(error['code'], error['message'], http_status=403)

def _main_process():
    row = ProcessDefinition.objects.filter(definition_code=BUSINESS_PROCESS, active=True,
        business_domain='MES', document_type='ProductionWorkOrder').first()
    if row is None:
        _fail('COMPLETION_MAIN_PROCESS_REQUIRED', '须先具备现有正式生产流程，不能建立第二套业务流程。')
    _assert_hash(row)
    return serialize_definition(row, include_nodes=True)

def _counts():
    return {'completionTransitionCount': BusinessStateTransition.objects.filter(object_type=OBJECT).count(),
        'completionWorkflowInstanceCount': WorkflowInstance.objects.filter(document_type=OBJECT).count()}

def read_completion_configuration_catalog():
    definition = ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    return {'contractVersion': CONTRACT, 'configurationOnly': True,
        'businessProcessCode': BUSINESS_PROCESS, 'internalApprovalTemplateCode': PROCESS,
        'definition': serialize_definition(definition, include_nodes=True) if definition else None,
        'permissions': list(Permission.objects.filter(code__in=[r['code'] for r in PERMISSIONS])
            .order_by('code').values('id', 'code', 'name', 'module')), **_counts()}

@transaction.atomic
def register_completion_configuration_catalog(*, user, reason, request_identity):
    """Register three permission points and the internal shared approval template."""
    _admin(user)
    reason, identity = _request(reason, request_identity)
    main_before, counts_before = _main_process(), _counts()
    if not any(node['nodeCode']=='PRODUCTION_OPERATION_REPORT' and node['active']
            and node['businessActionCode']=='production.operation.report' for node in main_before['nodes']):
        _fail('COMPLETION_REPORT_NODE_REQUIRED','正式工序报工节点须先登记生效，才能接续完工审核。')
    definition = ProcessDefinition.objects.select_for_update().filter(definition_code=PROCESS).first()
    if ProcessDefinition.objects.filter(document_type=OBJECT, active=True).exclude(definition_code=PROCESS).exists():
        _fail('COMPLETION_TEMPLATE_AUTHORITY_CONFLICT', '已有其他完工审核模板，禁止建立第二份完工权威。')
    if definition:
        _assert_hash(definition)
        actual = serialize_definition(definition)
        if any(actual[key] != value for key, value in DEFINITION.items()):
            _fail('COMPLETION_TEMPLATE_CONFLICT', '既有同码完工审核模板内容不同，禁止覆盖。')
        if definition.nodes.exclude(node_code__in=[r['nodeCode'] for r in NODES]).exists():
            _fail('COMPLETION_TEMPLATE_NODE_CONFLICT', '完工内部模板存在未授权节点，禁止覆盖。')
    for expected in NODES:
        competing = WorkflowNodeDefinition.objects.filter(business_action_code=expected['businessActionCode'],
            active=True, process_definition__active=True)
        if definition:
            competing = competing.exclude(process_definition=definition, node_code=expected['nodeCode'])
        if competing.exists():
            _fail('COMPLETION_NODE_AUTHORITY_CONFLICT', '完工动作已绑定其他节点，禁止重复登记。')
        node = definition.nodes.filter(node_code=expected['nodeCode']).first() if definition else None
        if node and any(getattr(node, field) != expected[key] for key, field in (
            ('nodeName','node_name'),('sequence','sequence'),('businessActionCode','business_action_code'),
            ('active','active'),('description','description'))):
            _fail('COMPLETION_NODE_CONFLICT', '既有同码完工节点语义不同，禁止覆盖。')
    permission_created, audits = [], []
    for expected in PERMISSIONS:
        permission = Permission.objects.select_for_update().filter(code=expected['code']).first()
        if permission and (permission.name != expected['name'] or permission.module != expected['module']):
            _fail('COMPLETION_PERMISSION_CONFLICT', '既有同码完工权限含义不同，禁止覆盖。')
        if permission is None:
            permission = Permission.objects.create(**expected)
            audit = WorkflowDefinitionOperatingService._audit(user=user, action='REGISTER_OPERATION_COMPLETION_PERMISSION',
                target=permission, target_type='Permission', label=permission.name, reason=reason, before={},
                after={'permission': {'id': permission.pk, **expected}, 'configurationOnly': True,
                    'requestIdentity': identity, 'businessProcessCode': BUSINESS_PROCESS, **counts_before})
            permission_created.append(permission.pk); audits.append(audit.pk)
    workflow_results = []
    if definition is None:
        workflow_results.append(WorkflowDefinitionOperatingService.configure_atomic_minimal_template(user=user,
            payload={'definition': dict(DEFINITION), 'node': dict(NODES[0]), 'reason': reason}, idempotency_key=identity))
        definition = ProcessDefinition.objects.get(definition_code=PROCESS)
    for node in NODES:
        if not definition.nodes.filter(node_code=node['nodeCode']).exists():
            workflow_results.append(WorkflowDefinitionOperatingService.execute(user=user, action='SAVE_WORKFLOW_NODE',
                payload={**node, 'processDefinitionId': definition.pk, 'reason': reason}))
    definition.refresh_from_db(); _assert_hash(definition)
    if _main_process() != main_before or _counts() != counts_before:
        _fail('COMPLETION_CONFIGURATION_BUSINESS_CHANGED', '目录配置改变了原生产流程或完工业务事实，整个事务回滚。')
    return {**read_completion_configuration_catalog(), 'permissionCreatedIds': permission_created,
        'auditIds': audits, 'workflowResults': workflow_results, 'mainProcessUnchanged': True,
        'readbackVerified': True, 'humanAuthorizationWriteCount': 0}

def _account(user, account_id, expected_position_id):
    if type(account_id) is not int or type(expected_position_id) is not int or min(account_id, expected_position_id) <= 0:
        _fail('COMPLETION_CONFIGURATION_ID_INVALID', '须明确既有账号与岗位正整数身份。')
    account = User.objects.only('id','username','real_name','company_id','is_active','is_superuser')
    account = account.select_for_update().filter(pk=account_id, company_id=user.company_id,
        is_active=True, is_superuser=False).first()
    employees = list(formal_employee_queryset(company_id=user.company_id).filter(user_id=account_id)
        .select_related('position_ref','department_ref')[:2])
    employee = employees[0] if len(employees) == 1 else None
    now = timezone.now(); today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
    position = employee.position_ref if employee else None
    if not (account and employee and position and position.pk == expected_position_id and _effective(position,today)
            and _effective(employee.department_ref,today) and position.department_id == employee.department_ref_id
            and (employee.hire_date is None or employee.hire_date <= today)
            and (employee.leave_date is None or employee.leave_date > today)
            and (employee.resignation_date is None or employee.resignation_date > today)):
        _fail('COMPLETION_CONFIGURATION_EMPLOYMENT_REQUIRED', '账号须为当前公司唯一有效在职员工，且岗位与已确认责任岗位一致。')
    return account, employee, position, today

def _foundation(user, action, payload):
    response = AccessControlFoundationView().post(SimpleNamespace(user=user,
        data={'action': action, 'payload': {**payload, 'expectedActorId': user.pk}}))
    if response.status_code != 200 or not response.data.get('success'):
        error = response.data.get('error') or {'code':'COMPLETION_CONFIGURATION_FAILED','message':'正式权限维护失败。'}
        raise WorkflowDefinitionError(error['code'], error['message'], http_status=response.status_code)
    return response.data['data']['result']

@transaction.atomic
def configure_completion_participants(*, user, requester_account_id, requester_position_id,
        reviewer_account_id, reviewer_position_id, reason, request_identity):
    """Apply the caller's explicit existing-person choices using native guards."""
    _admin(user)
    reason, identity = _request(reason, request_identity)
    if len(identity)>100:
        _fail('COMPLETION_CONFIGURATION_REQUEST_REQUIRED','完整责任配置请求标识不得超过100字，以容纳原生维护子请求。')
    if requester_account_id == reviewer_account_id or requester_position_id == reviewer_position_id:
        _fail('COMPLETION_CONFIGURATION_SEPARATION_REQUIRED', '完工申请人与生产跟单员审核人必须为不同账号及岗位。')
    if not Company.objects.filter(pk=user.company_id,is_active=True).exists():
        _fail('COMPLETION_CONFIGURATION_COMPANY_REQUIRED','当前公司须启用。')
    request = _account(user, requester_account_id, requester_position_id)
    review = _account(user, reviewer_account_id, reviewer_position_id)
    catalog = register_completion_configuration_catalog(user=user, reason=reason, request_identity=identity+'-catalog')
    definition = ProcessDefinition.objects.get(definition_code=PROCESS)
    main_before, counts_before = _main_process(), _counts()
    results=[]
    for ordinal, (person, duty, node_spec, action, role_label) in enumerate(zip(
            (request, review), DUTIES, NODES, (REQUEST_ACTION, APPROVE_ACTION), ('工序完工申请员','工序完工审核员'))):
        account, employee, position, today = person
        code, name, description, ownership = duty
        def org(command, values, suffix):
            return OrganizationOperatingService.execute(user=user, action=command,
                payload={**values,'reason':reason}, request_identity=f'{identity}-{ordinal}-{suffix}')
        fields={'code':code,'name':name,'description':description,'businessDomain':'MES','effectiveFrom':today.isoformat()}
        responsibility=Responsibility.objects.select_for_update().filter(code=code).first()
        if responsibility is None:
            result=org('SAVE_RESPONSIBILITY',{**fields,'status':'DRAFT'},'draft')
            responsibility=Responsibility.objects.get(pk=result['target']['id'])
            org('SAVE_RESPONSIBILITY',{**fields,'id':responsibility.pk,'status':'ACTIVE'},'active')
            responsibility.refresh_from_db()
        if not (responsibility.name==name and responsibility.description==description and responsibility.category=='MES'
                and responsibility.status=='ACTIVE' and responsibility.is_active and _effective(responsibility,today)):
            _fail('COMPLETION_RESPONSIBILITY_CONFLICT','既有同码完工职责与授权方案不一致，禁止覆盖。')
        mapping=PositionResponsibility.objects.filter(position=position,responsibility=responsibility).first()
        if mapping is None:
            org('SAVE_POSITION_RESPONSIBILITY',{'positionId':position.pk,'responsibilityId':responsibility.pk,
                'isPrimary':False,'active':True},'position')
        elif not mapping.active:
            _fail('COMPLETION_POSITION_RESPONSIBILITY_CONFLICT','同岗位职责已停用，禁止静默恢复。')
        node=definition.nodes.get(node_code=node_spec['nodeCode'])
        matches=PositionWorkflowResponsibility.objects.filter(position=position,workflow_node=node)
        relation=matches.first()
        if relation is None:
            org('SAVE_WORKFLOW_RESPONSIBILITY',{'positionId':position.pk,'responsibilityId':responsibility.pk,
                'workflowNodeId':node.pk,'ownershipType':ownership,'active':True,'effectiveFrom':today.isoformat()},'node')
            relation=matches.get()
        if not (matches.count()==1 and relation.active and relation.ownership_type==ownership
                and relation.responsibility_id==responsibility.pk and relation.workflow_code==PROCESS
                and relation.node_code==node.node_code and _effective(relation,today)):
            _fail('COMPLETION_WORKFLOW_RESPONSIBILITY_CONFLICT','既有完工流程责任关系不同，禁止覆盖。')
        company=Company.objects.get(pk=user.company_id)
        role_name=f'{company.code} {role_label}'
        role_description=f'{CONTRACT}；仅本公司{role_label}，申请与审核角色分离，不含转移或后序放行。'
        role=Role.objects.select_for_update().filter(name=role_name).first()
        if role is None:
            result=_foundation(user,'SAVE_ROLE',{'name':role_name,'description':role_description,'reason':reason})
            role=Role.objects.get(pk=result['id'])
            _foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':[READ_PERMISSION,action],'reason':reason})
        if role.description!=role_description or set(RolePermission.objects.filter(role=role)
                .values_list('permission__code',flat=True))!={READ_PERMISSION,action}:
            _fail('COMPLETION_ROLE_CONFLICT','完工独立角色须精确包含查看及对应单一动作，禁止覆盖已有角色。')
        opposite=APPROVE_ACTION if action==REQUEST_ACTION else REQUEST_ACTION
        if UserRoleScopeAssignment.objects.filter(user=account,organization_id=user.company_id,active=True,
                role__rolepermission__permission__code=opposite).exists():
            _fail('COMPLETION_ROLE_SEPARATION_CONFLICT','所选账号已拥有对立完工动作，不能同时申请和审核。')
        preserved=list(UserRoleScopeAssignment.objects.filter(user=account).order_by('pk').values())
        payload={'userId':account.pk,'roleCode':role.code,'legalEntityId':str(user.company_id),
            'departmentId':None,'scopeCode':'ORGANIZATION','version':1}
        authority,created=UserRoleScopeAssignment.objects.select_for_update().get_or_create(user=account,role=role,
            organization_id=user.company_id,defaults={'department':None,'scope_code':'ORGANIZATION','active':True,
                'version':1,'business_hash':business_hash(payload)})
        if not (authority.active and authority.scope_code=='ORGANIZATION' and authority.department_id is None
                and authority.version==1 and authority.business_hash==business_hash(payload)):
            _fail('COMPLETION_SCOPE_CONFLICT','已有同角色范围与独立同公司授权不同，禁止覆盖。')
        if any(UserRoleScopeAssignment.objects.filter(pk=old['id']).values().get()!=old for old in preserved):
            _fail('COMPLETION_EXISTING_SCOPE_CHANGED','既有授权发生变化，配置事务回滚。')
        audit=None
        if created:
            audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,
                action_code='APPEND_OPERATION_COMPLETION_AUTHORITY',target_type='User',target_id=account.pk,
                target_label=f'{account.username} - {account.real_name}',reason=reason,
                before_snapshot={'preservedAuthorityIds':[row['id'] for row in preserved]},
                after_snapshot={'authority':{**payload,'id':authority.pk},'requestIdentity':identity,
                    'positionId':position.pk,'employeeId':employee.pk,'workflowNodeId':node.pk,
                    'ownershipType':ownership,'permissionCodes':[READ_PERMISSION,action],'configurationOnly':True})
        results.append({'accountId':account.pk,'employeeId':employee.pk,'positionId':position.pk,
            'responsibilityId':responsibility.pk,'workflowResponsibilityId':relation.pk,'ownershipType':ownership,
            'roleId':role.pk,'roleCode':role.code,'authorityId':authority.pk,'authorityCreated':created,
            'auditId':audit.pk if audit else None,'permissionCodes':[READ_PERMISSION,action]})
    if _main_process()!=main_before or _counts()!=counts_before:
        _fail('COMPLETION_CONFIGURATION_BUSINESS_CHANGED','责任配置改变了业务事实或原生产流程，事务回滚。')
    return {'contractVersion':CONTRACT,'configurationOnly':True,'catalog':catalog,'participants':results,
        'mainProcessUnchanged':True,'businessWrites':0,'actualCompletionWrites':0,'readbackVerified':True}
