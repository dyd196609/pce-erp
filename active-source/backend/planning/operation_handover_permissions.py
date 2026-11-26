"""One native authority for exact WC handover duties, never inferred from titles."""
from django.utils import timezone
from pde.models import WorkCenter
from pde.work_center_responsibility_models import WorkCenterResponsibilityScope
from pde.work_center_responsibility_service import ObjectFacts,actor_for,scope_history
from system.models import PositionResponsibility
from workflow_runtime.models import ProcessDefinition
from workflow_runtime.action_permissions import ActionPermissionValidator
from .services import PlanningBusinessError
from .mes_test_source_bridge import _employees,_authority
from .mes_test_source_bridge import _effective

PROCESS='MES_OPERATION_HANDOVER'
NODES={kind:('PRODUCTION_OPERATION_HANDOVER_'+kind,'RESP_PROD_OPERATION_HANDOVER_'+kind+'_001') for kind in ('SOURCE','RECEIVE','REVIEW')}
DEFINITION={'definitionCode':PROCESS,'definitionName':'工序交接及产出确认职责模板','businessDomain':'MES',
    'documentType':'OperationHandover','version':1,'active':True,
    'description':'仅负责分批产出及实物交接；整体独审、后序开工、库存保持独立。'}
NODE_LABELS={'SOURCE':'来源工作中心交接负责人','RECEIVE':'目标工作中心接收负责人','REVIEW':'生产产出及异常独立确认'}
NODE_ACTIONS={'SOURCE':'production.operation.handover.dispatch','RECEIVE':'production.operation.handover.receive','REVIEW':'production.operation.output.excess.review'}
NODE_SPECS=[{'nodeCode':NODES[k][0],'nodeName':NODE_LABELS[k],'sequence':i+1,'businessActionCode':NODE_ACTIONS[k],
    'active':True,'description':NODE_LABELS[k]+'，按准确工作中心及本人职责范围核验。'} for i,k in enumerate(('SOURCE','RECEIVE','REVIEW'))]

def verified_node(kind):
    """Fresh maintained definition content AND canonical version must both match."""
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs();process=inputs.definition() if inputs is not None else NotImplemented
    indexed=process is not NotImplemented
    if not indexed:process=ProcessDefinition.objects.filter(definition_code=PROCESS,active=True,business_domain='MES',document_type='OperationHandover').first()
    if process is None:return None,None,'正式工序交接模板尚未配置生效。'
    from .mes_test_source_bridge import _assert_hash
    from workflow_runtime.definition_service import _canonical_hash,WorkflowDefinitionError
    try:_assert_hash(process)
    except WorkflowDefinitionError:return process,None,'正式工序交接模板内容与保存Hash不一致。'
    if process.definition_hash!=_canonical_hash({**DEFINITION,'nodes':NODE_SPECS}):
        return process,None,'正式工序交接模板版本或节点内容不符合当前正式合同。'
    node=(next((row for row in process.nodes.all() if row.node_code==NODES[kind][0]
        and row.active and row.business_action_code==NODE_ACTIONS[kind]),None) if indexed else
        process.nodes.filter(node_code=NODES[kind][0],active=True,business_action_code=NODE_ACTIONS[kind]).first())
    return process,node,'' if node else '正式工序交接动作节点身份不一致。'

def category(action):
    if action.endswith('.read'):return None
    if action.endswith('excess.report'):return 'REPORTER'
    if action.endswith('.receive'):return 'RECEIVE'
    if action.endswith(('excess.review','output.correct','exception.confirm')):return 'REVIEW'
    return 'SOURCE'

def check_action(*,user,action_code,work_center_id=None,object_type=None,object_id=None,status='open'):
    actor=actor_for(user);issues=[]
    now=timezone.now();today=timezone.localdate(now) if timezone.is_aware(now) else now.date()
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs()
    center=inputs.center(actor,work_center_id) if inputs is not None and work_center_id else NotImplemented
    if center is NotImplemented:
        center=WorkCenter.objects.filter(pk=work_center_id,company_id=actor.company_id,is_active=True).select_related('workshop').first() if work_center_id else None
    if work_center_id and (not center or not center.workshop_id or not center.workshop.is_active):issues.append('准确工作中心或车间不在当前有效公司范围。')
    dept=(center.workshop.department_id or center.department_id) if center and center.workshop_id else None
    # These are WC/company custody documents, not a personal-task inbox. A
    # directory or arbitrary document must never become "self owned" merely
    # because the caller's own ID was supplied as the object owner.
    kind=category(action_code)
    allowed,matched,native=_authority(actor,action_code,dept,None if kind is None else actor.pk)
    if action_code.startswith('production.operation.output.'):
        from .operation_output_contract import action_contract
        module='production-operation-output';key=action_code.removeprefix('production.operation.output.')
    else:
        from .operation_handover_contract import action_contract
        module='production-operation-handover';key=action_code.removeprefix('production.operation.handover.')
    contract=action_contract(key,object_id)
    fact_id=object_id if object_id is not None else (center.pk if center else actor.company_id)
    decision=ActionPermissionValidator(fact_provider=ObjectFacts(actor,module,fact_id,status)).evaluate(user=actor,
        module_code=module,action_code=action_code,object_ids=[fact_id],selection_count=1,requested_legal_entity_id=str(actor.company_id))
    if not allowed or not decision['granted']:issues.append('缺少同一正式角色的动作权限及当前公司／对象范围。')
    employee,position,department,assigned,evidence=_employees(actor)
    mapping=None;scope=None;node=None;process=None
    if kind is None:
        # Read permission alone is not a company-wide MES directory grant.
        # Reuse the existing exact duty/WC qualifications for the same actor.
        readable=[]
        if center:
            for delegated in ('production.operation.output.confirm','production.operation.handover.receive',
                              'production.operation.output.excess.review'):
                candidate=check_action(user=actor,action_code=delegated,work_center_id=center.pk,
                    object_type=object_type,object_id=object_id,status=status)
                if candidate['ready'] and set(candidate['roleCodes']) & {x['roleCode'] for x in matched}:
                    readable.append(candidate)
        if not readable:issues.append('读取须具备本工作中心有效产出、接收或独立审核职责及同角色查看权限。')
        else:evidence['readScopeEvidence']=[x['currentActorEvidence'] for x in readable]
    if kind is not None:
        employment=bool(employee and position and department and _effective(position,today) and _effective(department,today)
            and position.company_id==department.company_id==actor.company_id and position.department_id==department.pk
            and (employee.hire_date is None or employee.hire_date<=today)
            and (employee.leave_date is None or employee.leave_date>today)
            and (employee.resignation_date is None or employee.resignation_date>today))
        if not employment:issues.append('账号须对应唯一有效在职员工及正式岗位。')
        if kind=='REPORTER':
            process,node,template_issue=verified_node('SOURCE')
            if template_issue:issues.append(template_issue)
            evidence['qualificationMode']='FORMAL_FROZEN_REPORTER_NOT_WC_OWNER'
            # Exact frozen task/starter and original report authority are additionally checked by the output service.
            report_allowed,report_matched,_=_authority(actor,'production.operation.report',dept,actor.pk)
            if not report_allowed or not set(x['roleId'] for x in matched)&set(x['roleId'] for x in report_matched):
                issues.append('补充报工仍须同一正式角色具有原报工权限及范围。')
        elif center is None:issues.append('此动作必须绑定准确的有效工作中心。')
        else:
            node_code,duty_code=NODES[kind]
            process,node,template_issue=verified_node(kind)
            if template_issue:issues.append(template_issue)
            if position and node:
                rows=inputs.scopes(actor,position,PROCESS) if inputs is not None else NotImplemented
                if rows is NotImplemented:
                    rows=WorkCenterResponsibilityScope.objects.filter(company_id=actor.company_id,work_center=center,status='active',
                        workflow_responsibility__position=position,workflow_responsibility__responsibility__code=duty_code,
                        workflow_responsibility__workflow_node=node,workflow_responsibility__workflow_code=PROCESS,
                        workflow_responsibility__node_code=node_code,workflow_responsibility__ownership_type='OWNER',workflow_responsibility__active=True
                        ).select_related('workflow_responsibility__responsibility')
                else:
                    rows=[r for r in rows if r.work_center_id==center.pk
                        and r.workflow_responsibility.responsibility.code==duty_code
                        and r.workflow_responsibility.workflow_node_id==node.pk
                        and r.workflow_responsibility.node_code==node_code]
                valid=[]
                for row in rows:
                    m=row.workflow_responsibility
                    if row.employee_id is None:
                        from pfm.formal_employee import formal_employee_queryset
                        count=inputs.position_employee_count(actor,m.position_id) if inputs is not None else NotImplemented
                        if count is NotImplemented:count=formal_employee_queryset(company_id=actor.company_id).filter(position_ref_id=m.position_id).count()
                        if count!=1:continue
                    if (row.employee_id in (None,employee.pk if employee else None) and _effective(row,today)
                        and _effective(m,today) and _effective(m.responsibility,today)
                        and m.responsibility.status=='ACTIVE' and m.responsibility.is_active):
                        membership=inputs.duty_membership(actor,position) if inputs is not None else NotImplemented
                        has_duty=(m.responsibility_id in membership if membership is not NotImplemented else
                            PositionResponsibility.objects.filter(position=position,responsibility=m.responsibility,active=True).exists())
                        if has_duty:scope_history(row,actor=actor);valid.append(row)
                if len(valid)==1:scope=valid[0];mapping=scope.workflow_responsibility
            if not scope:issues.append('当前人员缺少本工作中心、准确动作节点的唯一有效负责人绑定。')
            if kind in ('SOURCE','RECEIVE') and position and position.workshop_id and position.workshop_id!=center.workshop_id:
                issues.append('正式岗位车间与当前办理工作中心不一致。')
    role_codes=sorted({x['roleCode'] for x in matched})
    evidence.update(currentEmploymentValid=bool(employee and position),workCenterId=center.pk if center else None,
        workCenterResponsibilityScopeId=scope.pk if scope else None,workflowResponsibilityId=mapping.pk if mapping else None,
        matchedAuthorityEvidence=matched,matchedRoleCodes=role_codes)
    return {'ready':not issues,'missingItems':issues,'issues':issues,'statusLabel':'当前动作正式资格已核实' if not issues else '；'.join(issues),
        'currentActorEvidence':evidence,'authorization':{**native,'roleCodes':role_codes},'roleCodes':role_codes,
        'definitionId':process.pk if process else None,'nodeId':node.pk if node else None,
        'definitionHash':process.definition_hash if process else None,'actionContract':contract,'decision':decision}

def require_action(**kwargs):
    q=check_action(**kwargs)
    if not q['ready']:raise PlanningBusinessError('HANDOVER_ACTION_DENIED',q['statusLabel'],http_status=403)
    return q

def reviewer_role_for(*,user,action_code='production.operation.output.excess.review',work_center_id):
    actor=actor_for(user)
    from pfm.formal_employee import formal_employee_queryset
    scopes=WorkCenterResponsibilityScope.objects.filter(company_id=actor.company_id,work_center_id=work_center_id,status='active',
        workflow_responsibility__node_code=NODES['REVIEW'][0],workflow_responsibility__workflow_code=PROCESS,
        workflow_responsibility__active=True).select_related('workflow_responsibility')
    codes=set()
    for scope in scopes:
        employees=formal_employee_queryset(company_id=actor.company_id).filter(position_ref_id=scope.workflow_responsibility.position_id)
        if scope.employee_id:employees=employees.filter(pk=scope.employee_id)
        for employee in employees.select_related('user'):
            if not employee.user_id:continue
            q=check_action(user=employee.user,action_code=action_code,work_center_id=work_center_id,
                object_type='OperationOutputEvidence',object_id=work_center_id,status='declared')
            if q['ready']:codes.update(q['roleCodes'])
    if len(codes)!=1:raise PlanningBusinessError('HANDOVER_REVIEW_ROLE_UNRESOLVED','本工作中心独立审核角色缺失或不唯一，请正式维护后再办理。',http_status=409)
    return next(iter(codes))
