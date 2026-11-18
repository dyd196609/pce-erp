"""Navigation selects candidates; native source and duty checks decide visibility."""
from .workshop_task_models import ProductionWorkshopTask as Task


def owned_tasks(actor):
    from .test_assignee_entry import owned_tasks as test_owned
    from .mes_test_source_bridge import _source
    from .operation_start_service import _qualification
    _,result=test_owned(actor)
    records=Task.objects.filter(company_id=actor.company_id,status='dispatched',
        execution_employee__user_id=actor.pk,work_order__usage_purpose='PRODUCTION_USE').select_related(
        'work_order__production_plan','source_operation','work_center','workshop')
    for task in records:
        # Waiting is only a duty capability query. The actual start separately
        # verifies current predecessor completion, state and source again.
        q=_qualification(actor,task,{'ready':True},{'ready':True},state='waiting')
        if q['ready']:
            _source(task,actor)
            result.append(task)
    return actor,result


def formal_graph(order):
    from .test_work_order_service import require_formal_work_order
    from .mes_formal_route import route_nodes
    require_formal_work_order(order)
    nodes=route_nodes(order)
    tasks=list(Task.objects.filter(work_order=order).select_related('source_operation'))
    byseq={t.source_operation.sequence:t for t in tasks}
    edges=[]
    for target in tasks:
        pending=list(nodes[target.source_operation.sequence]['frozenPredecessors']);seen=set()
        while pending:
            seq=pending.pop()
            if seq in seen:continue
            seen.add(seq);node=nodes[seq]
            if node['row']['decision']=='NOT_APPLICABLE':pending.extend(node['frozenPredecessors'])
            elif seq in byseq:edges.append((byseq[seq],target))
    omissions=[{'sequence':seq,'decisionLabel':'已核实本单不经过'} for seq,node in nodes.items() if node['row']['decision']=='NOT_APPLICABLE']
    return tasks,edges,omissions


def dispatch_entries(actor):
    """Read native, received workshop sources; navigation grants no authority."""
    from . import work_order_workshop_receipt_service as receipts
    from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt
    from .workshop_task_service import read_workshop_tasks, _dispatcher
    from .workshop_task_contract import READ_PERMISSION, SAVE_ACTION
    from .services import PlanningBusinessError
    from pde.order_routing_execution_service import ArrangementError
    from pde.plan_step_context_service import PlanStepContextError
    _, _, _, workshop, _ = receipts._employees(actor)
    if workshop is None or not receipts._authority(actor, READ_PERMISSION, workshop.department_id, None)[0]:
        return [], []
    links, blocked = [], []
    records = ProductionWorkOrderWorkshopReceipt.objects.filter(
        company_id=actor.company_id, workshop=workshop,
        work_order__usage_purpose='PRODUCTION_USE').select_related('work_order').order_by('work_order_id')
    for receipt in records:
        order = receipt.work_order
        if not _dispatcher(actor, order, workshop, SAVE_ACTION, order.pk, 'released')['ready']:
            continue
        try:
            facts = read_workshop_tasks(user=actor, work_order_id=order.pk)
        except (PlanningBusinessError, ArrangementError, PlanStepContextError) as error:
            blocked.append({'workOrderNo': order.no, 'code': error.code,
                'message': getattr(error, 'message', str(error))})
            continue
        for option in facts['operationOptions']:
            if option['sourceConsistent']:
                links.append({'label': order.no+' · '+option['operationName']+' · 本车间任务准备及派工记录',
                    'pageUrl': '/planning/workshop-tasks?workOrderId='+str(order.pk)+'&operationId='+str(option['id'])})
    return links, blocked
