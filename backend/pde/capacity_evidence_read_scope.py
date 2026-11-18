"""GET-owned raw evidence references; no authorization decisions are indexed."""
from contextvars import ContextVar
from functools import wraps
_scope=ContextVar('capacity_evidence_read_scope',default=None)

def evidence_cache(company_id):
    from planning.operation_predecessor_authority import _context,_proof_cache_epoch
    state=_scope.get();context=_context.get()
    if state is None or context is None or state['cache'].company_id!=company_id:return None
    epoch=_proof_cache_epoch(context)
    if epoch is None:return None
    if state['epoch']!=epoch:
        state['cache'].invalidate_proofs();state['epoch']=epoch
    return state['cache']

def capacity_evidence_scope(function):
    @wraps(function)
    def read(*args,**kwargs):
        from pde.routing_read_context import _current
        from .operation_requirement_service import _ReadOnlyProofCache
        from planning.operation_predecessor_authority import _context,_proof_cache_epoch
        request,context=_current.get(),_context.get()
        if not request or request.get('__http_get_read__') is not True or context is None or _scope.get() is not None:
            return function(*args,**kwargs)
        token=_scope.set({'cache':_ReadOnlyProofCache(kwargs['user']),'epoch':_proof_cache_epoch(context)})
        try:return function(*args,**kwargs)
        finally:_scope.reset(token)
    return read

def prefetch_edges(rows,cache):
    if cache is None:return
    from masterdata.models import MasterDataWriteRequest as Request
    from system.models import OrganizationOperatingAuditRecord as Audit
    from .manufacturing_capacity_scope import CONTRACT
    from .operation_requirement_service import _today
    ids={str(row.pk) for row in rows if isinstance(row.conditions,dict) and 'capacityUsageScope' in row.conditions}
    if not ids:return
    ledgers=list(Request.objects.filter(organization_id=cache.company_id,entity_type='standard-capacities',
        action_code='production.master_data.create',status=Request.Status.COMMITTED,target_entity_id__in=ids
        ).select_related('source_identity').order_by('pk'))
    grouped={}
    for ledger in ledgers:grouped.setdefault(ledger.target_entity_id,[]).append(ledger)
    aids={x.result['auditId'] for x in ledgers if isinstance(x.result,dict) and type(x.result.get('auditId')) is int}
    audits={x.pk:x for x in Audit.objects.filter(pk__in=aids,organization_id=cache.company_id,
        action_code='production.master_data.capacity.maintain',target_type='StandardCapacity').select_related('actor').defer('actor__password')}
    for row in rows:
        if str(row.pk) not in ids:continue
        key=(CONTRACT,'raw',row.company_id,cache.user_id,_today(),type(row).__name__,row.pk)
        matches=grouped.get(str(row.pk),[])
        cache[(*key,'ledgers','standard-capacities','production.master_data.create',Request.Status.COMMITTED,str(row.pk))]=matches
        for ledger in matches:
            aid=ledger.result.get('auditId') if isinstance(ledger.result,dict) else None
            if type(aid) is int:
                audit=audits.get(aid)
                cache[(*key,'audit',aid,'production.master_data.capacity.maintain',type(row).__name__,row.pk)]=audit if audit and audit.target_id==row.pk else None
