"""A08 read projection of an already-authorized order and native M09 proofs.

No new completion, quantity, permission or workflow authority. This internal
consumer receives M09 facts only from SalesOrderDetailView, after its original
sales.order.view and order scope check; never from an HTTP request body.
"""
from copy import deepcopy
import logging
from django.db import DatabaseError
from django.utils import timezone
from planning.operation_resource_read_scope import scoped_execution_read
from pde.order_lifecycle_source_projection import terminal_closure_read

CONTRACT = 'PCE-ORDER-INTERNAL-PROGRESS-V1'


def _failure(exc, scope, object_id):
    failed = isinstance(exc, DatabaseError)
    logging.getLogger(__name__).warning('A08 %s %s: %s', scope, object_id, type(exc).__name__)
    return {'factStatus': 'READ_FAILED' if failed else 'SOURCE_UNKNOWN',
        'code': 'A08_RECORD_READ_FAILED' if failed else getattr(exc, 'code', 'A08_RECORD_PROOF_UNPROVEN'),
        'message': '原始记录读取失败，结果未知。' if failed else '原始记录的来源或审计证明待核，未推定完成。',
        'scope': scope, 'objectId': object_id}


def _task_progress(task, quantity_fact, order_id):
    from system.models import User
    from planning.operation_start_models import ProductionOperationStart
    from planning.operation_completion_v3_authority import validated_bundle, current_production_status
    from planning.operation_completion_service import _history
    from planning.operation_report_service import _reports
    from planning.mes_task_date_facts import task_date_facts
    from planning.operation_handover_models import OperationHandover
    from planning.operation_handover_facts import _header
    from workflow_runtime.models import BusinessStateTransition
    row={'taskId':task.pk, 'taskNo':task.no, 'taskVersion':task.version,
        'operationId':task.source_operation.operation_id, 'sequence':task.source_operation.sequence,
        'operationName':task.source_operation.source_snapshot.get('operationName') or task.source_operation.operation.name,
        'operationNameSource':'frozen operationName' if task.source_operation.source_snapshot.get('operationName') else 'same native Process.name (current master)',
        'workshopId':task.workshop_id, 'workshopName':task.workshop.name,
        'workCenterId':task.work_center_id, 'workCenterName':task.work_center.name,
        'executionMode':task.execution_mode, 'quantityFacts':deepcopy(quantity_fact),
        'statusLabel':task.get_status_display(), 'completion':None, 'currentProduction':None,
        'reports':None, 'executionConfirmation':None, 'handovers':None, 'blockingReasons':[],
        'physicalCompletedAt':None, 'physicalCompletedAtStatus':'NOT_COLLECTED',
        'recordLocator':{'salesOrderId':order_id, 'taskId':task.pk,
            'api':f'/api/sales/orders/{order_id}/?includeProgressFacts=1&progressTaskId={task.pk}'}}
    times=[task.updated_at]
    start=ProductionOperationStart.objects.filter(task=task,company_id=task.company_id).first()
    dates=task_date_facts(task,None)
    row['start']=None
    try:
        if start:
            actor=User.objects.defer('password').get(pk=start.started_by_id)
            bundle=validated_bundle(task,actor)
            row['currentSourceReady']=bundle['source']['ready']
            row['currentSourceStatusLabel']=bundle['source'].get('statusLabel')
            row['start']={'id':start.pk,'statusLabel':start.get_status_display(),
                'operatorId':start.started_by_id,'occurredAt':start.started_at.isoformat(),
                'recordedAt':start.created_at.isoformat()}
            times.append(start.created_at)
            recorded_dates=[]
            if task.execution_mode=='QUANTIFIED':
                reports,_=_reports(task,start,recorded_dates=recorded_dates)
                allowed=('id','taskId','statusLabel','quantity','quantityPrecision','uomId','uomLabel',
                    'reportedById','reportedByLabel','reportedAt','reportedAtLabel','reason','auditReference',
                    'version','statusTransitionCount','statusTransitionHistory','stateMachineConsistent')
                row['reports']=[{k:r.get(k) for k in allowed} for r in reports]
                times.extend(r['recordedAt'] for r in recorded_dates)
            else:
                row['reports']=[]
                confirmation=bundle.get('executionConfirmation')
                allowed=('id','ref','proofType','taskId','startRecordId','confirmedById','confirmedByLabel',
                    'confirmedAt','confirmedAtLabel','reason','auditReference','statusLabel',
                    'statusTransitionHistory','statusTransitionCount','stateMachineConsistent','quantityApplicable')
                row['executionConfirmation']={k:deepcopy(confirmation[k]) for k in allowed if k in confirmation} if confirmation else None
                if confirmation:
                    times.extend(BusinessStateTransition.objects.filter(pk=confirmation['id']).values_list('timestamp',flat=True))
            dates=task_date_facts(task,start,report_dates=recorded_dates)
            try:
                completion=_history(task,bundle)
                allowed=('statusCode','statusLabel','generationId','generationVersion','projectionVersion',
                    'applicantId','applicantLabel','requestedAtLabel','requestAuditReference','reviewerId',
                    'reviewerLabel','completedAtLabel','approvalAuditReference','approvalDecisionId',
                    'workflowInstanceId','approvalTaskId','stateMachineConsistent','statusTransitionCount',
                    'statusTransitionHistory','completionProtocolVersion','closure')
                row['completion']={k:deepcopy(completion[k]) for k in allowed if k in completion} if completion else None
                row['completionReadStatus']='PROVIDED' if completion else 'NO_CURRENT_APPLICATION'
                row['completionStatusLabel']=completion['statusLabel'] if completion else '已本人开工，尚无当前完工申请'
                row['currentProduction']=current_production_status(task,actor,completion)
                dates=task_date_facts(task,start,report_dates=recorded_dates,completion=completion)
                ids=[r['id'] for r in (completion or {}).get('statusTransitionHistory',[]) if 'id' in r]
                times.extend(BusinessStateTransition.objects.filter(pk__in=ids).values_list('timestamp',flat=True))
            except DatabaseError:
                raise
            except Exception as exc:
                row['completionReadStatus']='SOURCE_UNKNOWN';row['completionStatusLabel']='完工证明待核'
                row['blockingReasons'].append(_failure(exc,'TASK_COMPLETION',task.pk))
        else:
            row.update(reports=[],completionReadStatus='NOT_STARTED',completionStatusLabel='尚无本人开工记录')
    except DatabaseError:
        raise
    except Exception as exc:
        row['blockingReasons'].append(_failure(exc,'TASK_EXECUTION',task.pk))
        row['completionReadStatus']='SOURCE_UNKNOWN';row['completionStatusLabel']='执行来源待核'
    handovers=[]
    for header in OperationHandover.objects.filter(company_id=task.company_id,data__taskId=task.pk).order_by('pk'):
        try:
            proof=_header(header)
            allowed=('id','no','taskId','workOrderId','statusLabel','receiptStateLabel','version','uomId','uomLabel',
                'senderEmployeeId','senderEmployeeName','receiverEmployeeId','receiverEmployeeName',
                'sourceWorkshopId','targetWorkshopId','sourceOperationName','targetOperationName',
                'dispatchedAt','lastReceivedAt','historicalDispatches','historicalReceipts',
                'sentQuantity','receivedQuantity','inTransitQuantity','shortQuantity','unmatchedQuantity',
                'currentTargetHeldQuantity','receiptMetricBasisLabel','receiptStateExplanation','receiptCorrectionReferences')
            handovers.append({k:deepcopy(proof[k]) for k in allowed if k in proof});times.append(header.updated_at)
        except DatabaseError:
            raise
        except Exception as exc:
            handovers.append({'id':header.pk,'no':header.no,'factStatus':'SOURCE_UNKNOWN',
                'blockingReason':_failure(exc,'HANDOVER',header.pk)})
    row['handovers']=handovers;row['dates']=dates
    row['progressUpdatedAt']=max(times).isoformat()
    row['progressUpdatedAtMeaning']='本投影已核实任务/开工/报工/审核/交接记录的最近登记更新时间；不是现场实际完工时间'
    row['factStatus']='SOURCE_UNKNOWN' if row['blockingReasons'] or any(x.get('factStatus')=='SOURCE_UNKNOWN' for x in handovers) else 'PROVIDED'
    return row


@terminal_closure_read
def _work_order_progress(fact,item,order, *, selected_task_id=None):
    from planning.work_order_models import ProductionWorkOrder
    from planning.workshop_task_models import ProductionWorkshopTask
    wo=ProductionWorkOrder.objects.select_related('production_plan__planning_requirement','material','uom').get(
        pk=fact['workOrderId'],company_id=order.company_id)
    ids=[x['taskId'] for x in fact['tasks']]
    if selected_task_id is not None:
        ids = [selected_task_id]
    tasks=list(ProductionWorkshopTask.objects.filter(pk__in=ids,work_order=wo,company_id=order.company_id).select_related(
        'source_operation__operation','workshop','work_center','work_order__source_schedule').order_by('source_operation__sequence','pk'))
    if {t.pk for t in tasks}!=set(ids):raise ValueError('A08_TASK_SET_CHANGED')
    quantities={x['taskId']:x for x in fact['tasks']}
    return {'workOrderId':wo.pk,'workOrderNo':wo.no,'version':fact['version'],
        'productionPlanId':wo.production_plan_id,'productionPlanNo':wo.production_plan.plan_no,
        'demandId':wo.production_plan.planning_requirement.demand_id,
        'materialId':wo.material_id,'materialCode':wo.material.code,'materialName':wo.material.name,
        'uomId':wo.uom_id,'uomLabel':wo.uom.name,'quantity':fact['quantity'],
        'statusLabel':fact['statusLabel'],'executionCompleted':fact['executionCompleted'],
        'mesClosed':fact['mesClosed'],'blockingReasons':deepcopy(fact['blockingReasons']),
        'plannedStartDate':fact['plannedStartDate'],'plannedRequiredDate':fact['plannedRequiredDate'],
        'physicalCompletedAt':None,'physicalCompletedAtStatus':'NOT_COLLECTED',
        'tasks':[_task_progress(t,quantities[t.pk],order.pk) for t in tasks]}


@scoped_execution_read
def order_progress_facts(order,completion_facts, *, selected_task_id=None):
    """No calculation of percent, cross-task totals, or completion qualification."""
    if (completion_facts.get('salesOrderId')!=order.pk or completion_facts.get('companyId')!=order.company_id
        or completion_facts.get('salesOrderVersion')!=order.version):raise ValueError('A08_ORDER_PROOF_MISMATCH')
    items={x.pk:x for x in order.items.select_related('sales_order','material','uom')}
    lines=[];failed=False
    for fact in completion_facts.get('lines') or []:
        item=items[fact['salesOrderItemId']]
        line={'salesOrderItemId':item.pk,'lineNo':item.line_no,'materialId':item.material_id,
            'materialCode':item.material.code,'materialName':item.material.name,'uomId':item.uom_id,
            'uomLabel':item.uom.name if item.uom_id is not None else None,'quantity':fact['quantity'],'requiredDate':fact['requiredDate'],
            'completionStatus':fact['completionStatus'],'completionReady':fact['ready'],
            'supplyCoverage':deepcopy(fact.get('supplyCoverage')),'blockingReasons':deepcopy(fact['blockingReasons']),
            'workOrders':[]}
        for wo_fact in fact['workOrders']:
            if selected_task_id is not None and not any(task['taskId'] == selected_task_id for task in wo_fact['tasks']):
                continue
            try:
                line['workOrders'].append(_work_order_progress(wo_fact, item, order, selected_task_id=selected_task_id))
            except Exception as exc:
                failure=_failure(exc,'WORK_ORDER',wo_fact['workOrderId']);failed=failed or isinstance(exc,DatabaseError)
                line['workOrders'].append({'workOrderId':wo_fact['workOrderId'],'factStatus':failure['factStatus'],
                    'tasks':None,'blockingReasons':[failure]})
        lines.append(line)
    return {'contractVersion':CONTRACT,'companyId':order.company_id,'salesOrderId':order.pk,
        'orderNo':order.order_no,'salesOrderVersion':order.version,'statusLabel':order.get_status_display(),
        'completionEligibility':completion_facts['completionEligibility'],'completionAuthority':'original mesCompletionFacts (unchanged)',
        'lines':lines,'factStatus':'READ_FAILED' if failed else 'PROVIDED',
        'loadedAt':timezone.now().isoformat(),'progressPercent':None,'progressPercentStatus':'NOT_DEFINED',
        'quantityPolicy':'Original M09 line range union only; task quantity accounts keep own unit and responsibility; never sum across tasks',
        'businessWriteCount':0,'automaticallyChangesOrderStatus':False}
