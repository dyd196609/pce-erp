"""Formal order closure over exact native execution and physical input proofs."""
from copy import deepcopy
from decimal import Decimal
from .operation_handover_core import _hash,verify_record


def _returned_short_settlement(header, totals):
    """Consume existing native return/short proofs, never rewrite a receipt.

    This admits only a loss-free, actually returned short range. Losses and
    other difference settlements retain the existing closure block until their
    own product/source contract is established.
    """
    from .operation_handover_models import OperationHandover,OperationCustodyEvent,OperationCustodyException
    from .operation_handover_authority import verify_handover,short_resolution
    if (header.status!='closed_with_difference'
        or any(Decimal(totals[k])!=0 for k in ('inTransitQuantity','shortQuantity','unmatchedQuantity','lostQuantity'))
        or Decimal(totals['returnedBeforeReceiptQuantity'])<=0
        or Decimal(totals['sentQuantity'])!=Decimal(totals['receivedQuantity'])+Decimal(totals['returnedBeforeReceiptQuantity'])):
        return None
    short_rows=list(OperationCustodyException.objects.filter(handover=header,kind='SHORT').order_by('pk'))
    if not short_rows:return None
    resolutions=[]
    for row in short_rows:
        verify_record(row);proof=short_resolution(row)
        if row.status!='confirmed' or Decimal(proof['remainingQuantity'])!=0:return None
        resolutions.append({'exceptionId':row.pk,'sourceSnapshotHash':row.source_snapshot_hash,**proof})
    events=list(OperationCustodyEvent.objects.filter(handover=header,kind='RETURN_UNRECEIVED').order_by('pk'))
    if not events or sum(Decimal(e.quantity) for e in events)!=Decimal(totals['returnedBeforeReceiptQuantity']):return None
    returns=[]
    for event in events:
        verify_record(event)
        back=OperationHandover.objects.filter(pk=event.data.get('returnHandoverId'),company_id=header.company_id,
            kind='RETURN',previous_handover=header,data__taskId=header.data['taskId'],
            target_work_center_id=header.source_work_center_id,status='received').first()
        if not back:return None
        verify_handover(back)
        returns.append({'eventId':event.pk,'eventHash':event.event_hash,'returnHandoverId':back.pk,
            'returnSourceSnapshotHash':back.source_snapshot_hash,'returnedQuantity':event.quantity})
    return {'kind':'NATIVE_LOSS_FREE_SHORT_ACTUALLY_RETURNED','shortResolutions':resolutions,'actualReturns':returns}


def product_source(order):
    if order.usage_purpose=='TEST_BUSINESS':return deepcopy(order.source_snapshot['product'])
    return {k:deepcopy(order.source_snapshot[k]) for k in ('companyId','productionPlanId','salesOrderId',
        'salesOrderItemId','materialId','materialCode','materialName','quantity','uomId','uomCode','uomLabel')}


def current_closure(order):
    from system.models import User
    from .finished_goods_authority import task_graph
    from .operation_start_models import ProductionOperationStart as Start
    from .mes_test_source_bridge import _source
    from .operation_completion_v3_authority import read_quantitative_whole_coverage,validated_bundle
    from .operation_completion_quantity_account import production_snapshot,production_issues
    from .operation_completion_generation_models import OperationCompletionGeneration as Generation
    from .operation_completion_service import _history
    from .operation_handover_authority import verify_task_custody,verify_handover
    from .operation_handover_models import OperationCustodyEvent as Event,OperationHandover
    from .operation_predecessor_authority import predecessor_facts
    tasks,edges,terminal,nodes=task_graph(order);proofs=[];edge_proofs=[];blockers=[];physical_receipts=[];handover_proofs=[]
    for task in tasks:
        start=Start.objects.filter(task=task).first()
        if not start:blockers.append(task.no+'尚未本人开工');continue
        owner=User.objects.get(pk=start.started_by_id)
        source=_source(task,owner)
        if not source['ready']:blockers.append(task.no+'：'+source['statusLabel']);continue
        common={'taskId':task.pk,'taskVersion':task.version,'sourceSnapshotHash':task.source_snapshot_hash,
            'assignmentHash':task.assignment_hash,'startId':start.pk,'executionMode':task.execution_mode}
        if task.execution_mode=='QUANTIFIED':
            whole=read_quantitative_whole_coverage(task)
            generation=Generation.objects.filter(task=task,status='approved').first()
            production=production_snapshot(task,actor=owner)
            if (not whole['valid'] or not generation or production_issues(production)
                    or generation.production_revision!=production['revision'] or generation.production_hash!=production['hash']):
                blockers.append(task.no+'当前定量生产版本尚未有效独审完工');continue
            verify_task_custody(task)
            proofs.append({**common,'generationId':generation.pk,'generationVersion':generation.version,
                'productionRevision':production['revision'],'productionHash':production['hash'],
                'completionProofHash':_hash(whole['proof']),'approvedAt':generation.approval_decision.completed_at.isoformat()})
        else:
            bundle=validated_bundle(task,owner);completion=_history(task,bundle)
            if (not bundle['ready'] or not completion or completion['statusCode']!='completed'
                    or not completion.get('approvalDecisionId') or not bundle.get('executionConfirmation')
                    or bundle['snapshot'].get('quantityApplicable') is not False):
                blockers.append(task.no+'尚缺原生实际经过与独立审核完成证明');continue
            proofs.append({**common,'quantityApplicable':False,'physicalQuantityInvented':False,
                'executionConfirmation':deepcopy(bundle['executionConfirmation']),
                'completionSourceHash':completion['sourceSnapshotHash'],'approvalDecisionId':completion['approvalDecisionId']})
    if not blockers:
        # Every required or formally exempt predecessor remains an independently
        # proved native DAG edge. Physical stock stays rooted in quantified
        # output batches; a nonquantity step never creates a fabricated batch.
        for task in tasks:
            p=predecessor_facts(task)
            if not p['ready']:blockers.append(task.no+'前序实际经过／独审证明未通过')
            for previous,target in edges:
                if target.pk==task.pk:edge_proofs.append({'sourceTaskId':previous.pk,'targetTaskId':task.pk,
                    'wholeCompletionProofHash':_hash(p),'receiptProofs':[]})
        for header in OperationHandover.objects.filter(company_id=order.company_id,data__taskId__in=[t.pk for t in tasks]).order_by('pk'):
            physical_proof=verify_handover(header)
            settlement=_returned_short_settlement(header,physical_proof) if header.status=='closed_with_difference' else None
            if header.status not in ('received','cancelled') and settlement is None:
                blockers.append(header.no+'仍有未完成实物交接，不能结转成品')
            item={'id':header.pk,'version':header.version,'sourceSnapshotHash':header.source_snapshot_hash,
                'sourceTaskId':header.data['taskId'],'targetOperationId':header.target_operation_id,'status':header.status}
            if settlement is not None:item['differenceSettlement']=settlement
            handover_proofs.append(item)
        # The native output/input allocation verifier proves exact received
        # ranges, same order/company and consumption before confirming output.
        receipts=list(Event.objects.filter(company_id=order.company_id,task__work_order=order,
            kind__in=('RANGE_RECEIVED','RECEIVE')).order_by('pk'))
        for event in receipts:
            verify_record(event)
            physical_receipts.append({'eventId':event.pk,'sourceTaskId':event.task_id,
                'sourceSnapshotHash':event.source_snapshot_hash,'intentHash':event.intent_hash,
                'handoverId':event.handover_id,'kind':event.kind})
    body={'contractVersion':'PCE-NATIVE-MES-ORDER-CLOSURE-V1','usagePurpose':'PRODUCTION_USE','companyId':order.company_id,
        'workOrderId':order.pk,'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
        'terminalTaskId':terminal.pk,'routeProofHash':_hash(nodes),'product':product_source(order),'tasks':proofs,'edges':edge_proofs,
        'physicalReceipts':physical_receipts,'handoverProofs':handover_proofs}
    return {'ready':not blockers,'blockingReasons':blockers,'manifest':body,'hash':_hash(body),'terminalTask':terminal}
