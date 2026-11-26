"""Native MES proof consumer and native WMS receipt verifier; no status shortcuts."""
from copy import deepcopy
from decimal import Decimal
from django.db import connection
from .operation_handover_core import fail,_hash,verify_record,text
from .work_order_models import ProductionWorkOrder
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_start_models import ProductionOperationStart as Start
from .operation_handover_models import OperationOutputEvidence,OperationCustodyEvent
from .operation_completion_generation_models import OperationCompletionGeneration
from .operation_resource_read_scope import scoped_execution_read
from .test_operation_predecessor_authority import route_nodes
from .operation_dependency_graph import validate_graph
from .operation_handover_authority import verify_task_custody

def order_for(actor,order_id):
    from .mes_test_source_bridge import _rows
    order=ProductionWorkOrder.objects.select_related('material__base_uom','uom','source_schedule').filter(
        pk=order_id,company_id=actor.company_id,pk__in=_rows(actor).values_list('pk',flat=True)).first()
    if not order:fail('FG_TEST_SOURCE_REQUIRED','仅允许本公司具有完整原生来源的正式或TEST工单，不接受用途转换或伪造来源。',403)
    if order.usage_purpose=='PRODUCTION_USE':
        from .test_work_order_service import require_formal_work_order
        from .work_order_execution_service import _verify
        require_formal_work_order(order);_verify(order)
    return order

def task_graph(order):
    tasks=list(Task.objects.filter(work_order=order,company_id=order.company_id).select_related('work_order__source_schedule',
        'source_operation__effective_step','work_center','workshop').order_by('source_operation__sequence'))
    nodes=route_nodes(order);byseq={t.source_operation.sequence:t for t in tasks}
    expected={seq for seq,node in nodes.items() if node['row']['decision']!='NOT_APPLICABLE'}
    if set(byseq)!=expected or len(byseq)!=len(tasks):fail('FG_TASK_SET_UNPROVEN','必经任务与完整冻结路线不一致，不能结转成品。')
    edges=[];parents=set()
    for task in tasks:
        issue=validate_graph(nodes,task.source_operation.sequence)
        if issue:fail('FG_ROUTE_UNPROVEN',issue)
        pending=list(nodes[task.source_operation.sequence]['frozenPredecessors'])
        while pending:
            seq=pending.pop()
            if seq in byseq:edges.append((byseq[seq],task));parents.add(byseq[seq].pk)
            else:pending.extend(nodes[seq]['frozenPredecessors'])
    terminal=[t for t in tasks if t.pk not in parents]
    if len(terminal)!=1:fail('FG_UNIQUE_TERMINAL_REQUIRED','须有明确唯一成品终结工序；不按最大序号猜测。')
    return tasks,edges,terminal[0],nodes

@scoped_execution_read
def current_closure(order):
    if order.usage_purpose=='PRODUCTION_USE':
        from .finished_goods_formal_authority import current_closure as formal_closure
        return formal_closure(order)
    from system.models import User
    from .mes_test_source_bridge import _source
    from .operation_completion_v3_authority import read_quantitative_whole_coverage
    from .operation_completion_quantity_account import production_snapshot,production_issues
    from .test_mes_predecessor_proofs import execution_proof
    tasks,edges,terminal,nodes=task_graph(order);proofs=[];edge_proofs=[];blockers=[]
    from .mes_evidence_graph import prepare_tasks
    prepare_tasks(tasks)
    for task in tasks:
        starter=Start.objects.filter(task=task).first()
        if not starter:raise_missing='任务'+task.no+'尚未真实开工';blockers.append(raise_missing);continue
        owner=User.objects.defer('password').get(pk=starter.started_by_id)
        source=_source(task,owner)
        if not source['ready']:blockers.append(task.no+'：'+source['statusLabel']);continue
        if task.execution_mode!='QUANTIFIED':
            blockers.append(task.no+'须提供已验证的原生无统计量独审证明；不能编造正数量或跳过');continue
        whole=read_quantitative_whole_coverage(task)
        if not whole['valid']:blockers.append(task.no+'尚无有效独审完工');continue
        generation=OperationCompletionGeneration.objects.filter(task=task,status='approved').first()
        production=production_snapshot(task,actor=owner)
        issues=production_issues(production)
        if not generation or issues or generation.production_revision!=production['revision'] or generation.production_hash!=production['hash']:
            blockers.append(task.no+'当前生产版本与独审完工代次不一致');continue
        verify_task_custody(task)
        proofs.append({'taskId':task.pk,'taskVersion':task.version,'sourceSnapshotHash':task.source_snapshot_hash,
            'assignmentHash':task.assignment_hash,'startId':starter.pk,'generationId':generation.pk,'generationVersion':generation.version,
            'productionRevision':production['revision'],'productionHash':production['hash'],'completionProofHash':_hash(whole['proof']),
            'approvedAt':generation.approval_decision.completed_at.isoformat()})
    if not blockers:
        for previous,target in edges:
            proof=execution_proof(previous,target)
            if not proof['ready']:blockers.append('任务'+target.no+'缺少当前有效前置及对应批次接收');continue
            # Freeze immutable receipt events, not the changing header aggregate.
            receipts=[r for r in proof['receiptProofs'] if r['kind']!='NATIVE_PHYSICAL_HANDOVER_RECEIPT']
            edge_proofs.append({'sourceTaskId':previous.pk,'targetTaskId':target.pk,'receiptProofs':receipts,
                'wholeCompletionProofHash':proof['wholeCompletionProofHash']})
    body={'contractVersion':'PCE-NATIVE-MES-ORDER-CLOSURE-V1','usagePurpose':'TEST_BUSINESS','companyId':order.company_id,
        'workOrderId':order.pk,'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
        'terminalTaskId':terminal.pk,'routeProofHash':_hash(nodes),'product':deepcopy(order.source_snapshot['product']),
        'tasks':proofs,'edges':edge_proofs}
    return {'ready':not blockers,'blockingReasons':blockers,'manifest':body,'hash':_hash(body),'terminalTask':terminal}

def verify_frozen_closure(order,frozen):
    current=current_closure(order)
    if not current['ready'] or not isinstance(frozen,dict):fail('FG_CLOSURE_NO_LONGER_VALID','原生产执行完结证明当前未通过，禁止继续交接。')
    now=current['manifest']
    if order.usage_purpose=='PRODUCTION_USE':
        for key in ('physicalReceipts','handoverProofs'):
            if frozen.get(key)!=now.get(key):fail('FG_FORMAL_CUSTODY_PROOF_CHANGED','原正式交接及实收证明已变化，不能沿用成品准入。')
    for key in ('contractVersion','usagePurpose','companyId','workOrderId','workOrderVersion','workOrderSnapshotHash','terminalTaskId','routeProofHash','product','tasks'):
        if frozen.get(key)!=now.get(key):fail('FG_CLOSURE_VERSION_CHANGED','原工单、任务或当前独审生产版本已变化。')
    latest={(x['sourceTaskId'],x['targetTaskId']):x for x in now['edges']}
    if len(frozen.get('edges',[]))!=len(latest):fail('FG_CLOSURE_EDGE_CHANGED','原路线承接边已变化。')
    for edge in frozen['edges']:
        proof=latest.get((edge['sourceTaskId'],edge['targetTaskId']))
        if not proof or edge['wholeCompletionProofHash']!=proof['wholeCompletionProofHash'] or any(x not in proof['receiptProofs'] for x in edge['receiptProofs']):
            fail('FG_CLOSURE_RECEIPT_CHANGED','原有效接收批次已撤回、转出、失效或版本变化。')
    return current

def verify_warehouse_conversion(event):
    """Custody replay calls this minimal ledger proof, never the closure consumer.

    Avoid a cycle: the closure itself replays terminal custody, which now links
    this real WMS conversion. Full source freshness belongs to action admission.
    """
    from .finished_goods_models import ProductionFinishedGoodsTransfer as Transfer
    from procurement.models import WarehouseInbound,InventoryTransaction,InventoryBalance,InventoryLot
    from workflow_runtime.models import BusinessStateTransition
    from system.models import OrganizationOperatingAuditRecord
    from masterdata.models import MasterDataWriteRequest
    from .finished_goods_contract import CODES,codes_for
    row=Transfer.objects.filter(pk=event.data.get('finishedGoodsTransferId'),task_id=event.task_id,company_id=event.company_id,status='received').first()
    if not row:fail('FG_WMS_CONVERSION_UNPROVEN','末端保管转化缺少真实已接收成品交接单。')
    purpose=row.work_order.usage_purpose
    CODES=codes_for(purpose)
    verify_record(row)
    ledger=MasterDataWriteRequest.objects.filter(organization_id=row.company_id,entity_type='ProductionFinishedGoodsTransfer',
        target_entity_id=str(row.pk),action_code=CODES['receive'],request_hash=event.intent_hash,status='COMMITTED').first()
    if not ledger or ledger.audit_metadata.get('actorId')!=row.receiver_id:
        fail('FG_WMS_INTENT_UNPROVEN','成品保管转化缺少原接收意图的真实已提交账本。')
    stock=row.data.get('warehouseReceipt',{})
    inbound=WarehouseInbound.all_objects.filter(pk=stock.get('inboundId'),production_transfer=row,usage_purpose=purpose,status='completed').first()
    txn=InventoryTransaction.all_objects.filter(pk=stock.get('transactionId'),source_inbound=inbound,usage_purpose=purpose).first() if inbound else None
    lot=InventoryLot.all_objects.filter(pk=stock.get('lotId'),usage_purpose=purpose).first()
    balance=InventoryBalance.all_objects.filter(pk=stock.get('balanceId'),usage_purpose=purpose).first()
    if (not inbound or not txn or not lot or not balance or inbound.source_inspection_id is not None
        or inbound.warehouse_id!=row.warehouse_id or inbound.location_id!=row.location_id
        or inbound.operator_account_id!=row.receiver_id or inbound.operator_employee_id!=row.receiver_employee_id
        or txn.operator_account_id!=row.receiver_id or txn.operator_employee_id!=row.receiver_employee_id
        or txn.lot_id!=lot.pk or balance.lot_id!=lot.pk or txn.material_id!=row.material_id
        or lot.material_id!=row.material_id or lot.company_id!=row.company_id or lot.warehouse_id!=row.warehouse_id
        or balance.warehouse_id!=row.warehouse_id or balance.material_id!=row.material_id or balance.location_id!=row.location_id
        or txn.warehouse_id!=row.warehouse_id or txn.location_id!=row.location_id
        or txn.direction!='IN' or txn.quantity!=Decimal(row.quantity) or inbound.quantity!=Decimal(row.quantity)
        or txn.before_quantity+txn.quantity!=txn.after_quantity or balance.quantity!=txn.after_quantity
        or row.warehouse.usage_purpose!=purpose or row.sender_employee_id==row.receiver_employee_id or event.created_by_id!=row.receiver_id
        or event.data.get('warehouseReceipt')!=stock):fail('FG_WMS_CONVERSION_UNPROVEN','真实WMS来源、数量、用途、收方或余额事务不一致。')
    transitions=list(BusinessStateTransition.objects.filter(object_type='WarehouseInbound',object_id=inbound.pk).order_by('version','pk'))
    expected=[('','planned'),('planned','processing'),('processing','completed')]
    if len(transitions)!=3:fail('FG_WMS_STATE_UNPROVEN','测试生产入库缺少完整统一状态转换。')
    for index,(transition,pair) in enumerate(zip(transitions,expected),1):
        prefix='OrganizationOperatingAuditRecord:'
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=transition.audit_reference.removeprefix(prefix)).first() if transition.audit_reference.startswith(prefix) else None
        state=audit.after_snapshot.get('state',{}) if audit else {}
        if (transition.version!=index or (transition.source_state,transition.target_state)!=pair or transition.operator_id!=row.receiver_id
            or not audit or audit.actor_id!=row.receiver_id or audit.target_type!='WarehouseInbound' or audit.target_id!=inbound.pk
            or audit.organization_id!=row.company_id or audit.action_code!=transition.action_code or audit.action_code!=CODES['receive']
            or audit.reason!=transition.reason or audit.before_snapshot.get('state',{}).get('status')!=pair[0]
            or state.get('usagePurpose')!=purpose or state.get('status')!=pair[1]
            or state.get('productionTransferId')!=row.pk or state.get('warehouseId')!=row.warehouse_id or state.get('locationId')!=row.location_id
            or state.get('operatorEmployeeId')!=row.receiver_employee_id or Decimal(state.get('quantity','-1'))!=Decimal(row.quantity)
            or state.get('qualification',{}).get('ready') is not True or state.get('authorization',{}).get('allowed') is not True
            or state.get('actionPermissionDecision',{}).get('granted') is not True):fail('FG_WMS_STATE_UNPROVEN','测试生产入库审计与实际转换不一致。')
    return True
