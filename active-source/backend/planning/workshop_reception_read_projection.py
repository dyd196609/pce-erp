

# Native formal continuation: individually restored symbols; existing proofs preserved.
from .services import PlanningBusinessError

LEGACY_FULL='legacy-full'

SELECTED_DETAIL='selected-detail'

def latest_own_action_flag(raw):
    if raw in (None,'0'):
        return False
    if raw=='1':
        return True
    raise PlanningBusinessError('WORKSHOP_RECEPTION_LOCATOR_QUERY_INVALID',
        '最近正式办理定位标识仅允许0或1。',http_status=400)

def response_mode(value):
    if value is None:
        return LEGACY_FULL
    if value not in (LEGACY_FULL,SELECTED_DETAIL):
        raise PlanningBusinessError('WORKSHOP_RECEPTION_RESPONSE_MODE_INVALID',
            '接收读取模式无效；仅支持完整事实或工序目录与所选详情。',http_status=400)
    return value

def operation_directory_row(operation):
    return {'id':operation.pk,'operationId':operation.pk,'workOrderId':operation.work_order_id,
        'workOrderNo':operation.work_order.no,'sequence':operation.sequence,
        'operationName':operation.operation.name,
        'statusLabel':'工序目录；请选择本工序读取当前资源、接收及资格事实',
        'directoryOnly':True,'qualificationIncluded':False,'actionsIncluded':False,'proofsIncluded':False}

def validate_locator_request(enabled,mode):
    if type(enabled) is not bool or enabled and mode!=SELECTED_DETAIL:
        raise PlanningBusinessError('WORKSHOP_RECEPTION_LOCATOR_QUERY_INVALID',
            '最近正式办理只读定位须显式使用工序目录与所选详情模式。',http_status=400)

def latest_own_action_candidate(actor,operations):
    """Find a candidate identity only; native proof verification is mandatory."""
    from django.db.models import Q
    from system.models import OrganizationOperatingAuditRecord
    from .operation_resource_selection_contract import SELECT_ACTION,SELECT_OBJECT,RECEIVE_ACTION,RECEIVE_OBJECT
    from .operation_resource_handoff_contract import ACTION,OBJECT
    by_id={operation.pk:operation for operation in operations}
    if not by_id:
        return None
    kinds=(Q(action_code=SELECT_ACTION,target_type=SELECT_OBJECT)
        |Q(action_code=RECEIVE_ACTION,target_type=RECEIVE_OBJECT)|Q(action_code=ACTION,target_type=OBJECT))
    audit=OrganizationOperatingAuditRecord.objects.filter(kinds,organization_id=actor.company_id,
        actor_id=actor.pk,target_id__in=by_id).only('pk','organization_id','actor_id','action_code',
            'target_type','target_id','created_at').order_by('-created_at','-pk').first()
    return (by_id[audit.target_id],audit) if audit else None

def verified_view_location(actor,candidate,resource_facts):
    """A navigation hint over the current native proof; never an admission."""
    from .operation_resource_selection_contract import SELECT_ACTION,RECEIVE_ACTION
    from .operation_resource_handoff_contract import ACTION
    operation,audit=candidate
    fields={SELECT_ACTION:'resourceSelectionReference',RECEIVE_ACTION:'preciseReceiptReference',ACTION:'resourceHandoffReference'}
    proof=resource_facts.get(fields[audit.action_code])
    if audit.action_code==ACTION and proof is None:
        proof=resource_facts.get('resourceHandoff')
    handoff=resource_facts.get('resourceHandoffReference') or resource_facts.get('resourceHandoff')
    if (not isinstance(proof,dict) or proof.get('auditReference')!=f'OrganizationOperatingAuditRecord:{audit.pk}'
            or audit.actor_id!=actor.pk or audit.organization_id!=actor.company_id
            or any(resource_facts.get(key) is not True for key in ('currentResourceValid','masterDataConsistent','sourceUnchanged'))
            or resource_facts.get('changeRequired') is True and not handoff):
        raise PlanningBusinessError('WORKSHOP_RECEPTION_LOCATOR_PROOF_UNVERIFIED',
            '本账号最近正式办理记录的当前资源或证明尚未通过核对，已停止自动定位；不会改选其他工单或工序。',http_status=409)
    return {'kind':'LATEST_OWN_FORMAL_ACTION','actorId':actor.pk,'companyId':actor.company_id,
        'productionPlanId':operation.work_order.production_plan_id,'workOrderId':operation.work_order_id,
        'operationId':operation.pk,'actionCode':audit.action_code,'auditReference':f'OrganizationOperatingAuditRecord:{audit.pk}',
        'statusLabel':'根据本账号本工单最近正式办理记录定位'}

def view_location_fields(requested,suggestion=None):
    return {'viewLocationSuggestion':suggestion,
        'viewLocationStatus':'suggested' if suggestion else 'no_own_formal_action' if requested else 'not_requested',
        'viewLocationStatusLabel':suggestion['statusLabel'] if suggestion else
            '本账号在当前可见范围内尚无可定位的本人正式办理记录；未自动选择工单或工序' if requested else
            '按当前明确查看位置读取，未请求最近正式办理定位'}


# Native formal continuation: individually restored symbols; existing proofs preserved.
def current_native_read_cache(actor):
    """Reuse only the existing actor-bound native atomic read cache, if any."""
    from pde import operation_allocation_source_handoff_service as allocations
    context=allocations._scope.get()
    if (context is None or context['companyId']!=getattr(actor,'company_id',None)
            or context['userId']!=getattr(actor,'pk',None)):
        return None
    allocations._refresh(context)
    from pde.operation_requirement_service import _bind_current_actor
    return _bind_current_actor(context['cache'],actor)
