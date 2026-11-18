"""Read an approved source version through proved native lifecycle-only events.

This projects an object in memory for the ORIGINAL approval-proof verifier.
It never changes persisted status/version, content, audits or carry records.
"""
from copy import copy
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_terminal_read=ContextVar('m09_terminal_order_read',default=None)


def terminal_closure_read(function):
    @wraps(function)
    def run(work_order,item,*args,**kwargs):
        order=item.sales_order
        if order.status not in {'delivering','completed','closed'}:
            return function(work_order,item,*args,**kwargs)
        from pde.models import OrderReviewSalesOrderRelation
        from pde.crm_order_version_carry_forward import matching_proof,CarryForwardError
        relations=list(OrderReviewSalesOrderRelation.objects.filter(sales_order=order).select_related('sales_order'))
        valid=[]
        for relation in relations:
            try:
                if matching_proof(relation):valid.append(relation.pk)
            except CarryForwardError:pass
        if len(valid)!=1:
            raise CarryForwardError('终态只读闭合核验缺少唯一当前可证来源。')
        token=_terminal_read.set((order.pk,order.company_id,order.version,order.status))
        try:return function(work_order,item,*args,**kwargs)
        finally:_terminal_read.reset(token)
    return run


def terminal_read_allowed(order):
    return _terminal_read.get()==(order.pk,order.company_id,order.version,order.status)


def approved_source_relation(relation):
    from .crm_order_version_carry_forward import CarryForwardError
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    from sales.models import SalesOrderActionRequest
    from sales.services import ORDER_ACTIONS
    order = relation.sales_order
    if order.status == 'approved':
        return relation
    if order.status not in {'engineering', 'manufacturing_ready', 'in_progress', 'delivering', 'completed', 'closed'}:
        raise CarryForwardError('当前状态不属于已批准后原生执行生命周期。')
    events = list(BusinessStateTransition.objects.filter(object_type='SalesOrder', object_id=order.pk).order_by('version', 'pk'))
    approved = [e for e in events if e.target_state == 'approved' and e.action_code == 'sales.order.approve']
    if len(approved) != 1:
        raise CarryForwardError('批准后的来源承接缺少唯一原生批准转换。')
    tail = [e for e in events if e.version > approved[0].version]
    if not tail:
        raise CarryForwardError('生命周期状态缺少原生转换。')
    first = OrganizationOperatingAuditRecord.objects.filter(
        pk=tail[0].audit_reference.removeprefix('OrganizationOperatingAuditRecord:'),
        organization_id=order.company_id, target_type='SalesOrder', target_id=order.pk,
    ).first() if re.fullmatch(r'OrganizationOperatingAuditRecord:[1-9][0-9]*',tail[0].audit_reference or '') else None
    version = first.before_snapshot.get('state', {}).get('version') if first else None
    if type(version) is not int or version <= 0:
        raise CarryForwardError('生命周期来源版本缺少原生审计。')
    approved_version = version
    status = 'approved'
    event_version = approved[0].version
    allowed = {code: (states, target) for name,(code,states,target,_) in ORDER_ACTIONS.items()
               if name in {'start-engineering','complete-engineering','start-execution','start-delivery','complete','close'}}
    for event in tail:
        if not re.fullmatch(r'OrganizationOperatingAuditRecord:[1-9][0-9]*',event.audit_reference or ''):
            raise CarryForwardError('生命周期审计引用无效。')
        audit = OrganizationOperatingAuditRecord.objects.filter(
            pk=int(event.audit_reference.split(':')[1]), organization_id=order.company_id,
            target_type='SalesOrder',target_id=order.pk,action_code=event.action_code,actor_id=event.operator_id,
        ).first()
        before = audit.before_snapshot.get('state',{}) if audit else {}
        after = audit.after_snapshot.get('state',{}) if audit else {}
        auth = audit.after_snapshot.get('authorization',{}) if audit else {}
        request = SalesOrderActionRequest.objects.filter(sales_order=order,audit_record=audit,
            action_code=event.action_code,actor_id=event.operator_id,source_state=event.source_state,
            target_state=event.target_state,request_id=after.get('requestId',''),
            idempotency_key=after.get('idempotencyKey','')).first() if audit else None
        definition=allowed.get(event.action_code)
        if (not definition or status not in definition[0] or event.target_state!=definition[1]
            or event.source_state!=status or event.version!=event_version+1
            or before!={'status':status,'version':version} or after.get('status')!=event.target_state
            or not audit or event.reason!=audit.reason or not auth.get('allowed')
            or event.action_code not in auth.get('permissionCodes',[]) or not request):
            raise CarryForwardError('生命周期动作、权限、版本、审计或原动作请求不一致。')
        version+=1;event_version+=1;status=event.target_state
    if (version,status)!=(order.version,order.status):
        raise CarryForwardError('生命周期证明未覆盖当前实际状态和版本。')
    projected=copy(order);projected.version=approved_version;projected.status='approved'
    result=copy(relation);result._state=copy(relation._state);result._state.fields_cache=relation._state.fields_cache.copy()
    result.sales_order=projected
    return result
