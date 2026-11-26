"""Private raw dependency indexes for the current GET database epoch only."""
def read_rows(namespace,key,loader):
    from pde.routing_read_context import _current
    from .operation_predecessor_authority import _context,_proof_cache_epoch
    request,context=_current.get(),_context.get()
    if not request or request.get('__http_get_read__') is not True or context is None:return loader()
    epoch=_proof_cache_epoch(context)
    if epoch is None:return loader()
    identity=('custody_dependency_rows',namespace,epoch,key)
    if identity not in request:request[identity]=loader()
    return request[identity]

def task_events(task_id):
    from .operation_handover_models import OperationCustodyEvent
    return read_rows('events',task_id,lambda:list(OperationCustodyEvent.objects.filter(task_id=task_id).order_by('pk')))

def task_inputs(task_id):
    from .operation_handover_models import OperationInputAllocation
    def load():
        source=OperationInputAllocation.objects.filter(output__task_id=task_id)
        identities=list(source.values_list('pk',flat=True))
        rows=list(source.select_related('output__uom','execution_start','source_slice__root__task__source_operation',
            'source_slice__root__task__work_order__source_schedule','source_slice__root__task__workshop',
            'source_slice__root__task__work_center'))
        # A broken dependency must reach the native dereference/refusal path;
        # an inner join must never silently remove an allocation from proof.
        return rows if {row.pk for row in rows}==set(identities) else list(source)
    return read_rows('inputs',task_id,load)
