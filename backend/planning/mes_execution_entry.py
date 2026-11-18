from pde.routing_read_context import routing_read_request
"""Read-only MES navigation by existing effective duties; no new permission."""
from django.db.models import Count
from .operation_resource_read_scope import scoped_execution_read
from .mes_test_source_bridge import _actor, _authority
from .mes_native_navigation import owned_tasks
from .finished_goods_permissions import warehouse_qualification
from .operation_completion_v3_authority import reviewer_can_read
from .workshop_task_models import ProductionWorkshopTask as Task
from .finished_goods_models import ProductionFinishedGoodsTransfer as Transfer

@scoped_execution_read
def read_entry(user,work_order_id=None,directory=False):
    if work_order_id is not None and (type(work_order_id) is not int or work_order_id<=0):raise PlanningBusinessError('MES_ENTRY_QUERY_INVALID','工单须为准确正整数。',http_status=400)
    actor,_ = _actor(user)
    _,own = owned_tasks(actor)
    candidates=Task.objects.filter(company_id=actor.company_id,work_order__usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE')).select_related('work_order','workshop','work_center','source_operation','workload_uom')
    review=[]
    for task in candidates:
        if (_authority(actor,'production.operation.complete.read',task.workshop.department_id,actor.pk)[0]
                and reviewer_can_read(actor,task)):
            review.append(task)
    warehouse=warehouse_qualification(actor,required=False)['ready'] or warehouse_qualification(actor,required=False,purpose='PRODUCTION_USE')['ready']
    links=[]
    if own:
        first=str(own[0].pk)
        links += [{'label':'本人已完成及执行中的报工／开工记录','pageUrl':'/planning/operation-reports?taskId='+first},
            {'label':'本人范围产出确认及交接历史','pageUrl':'/planning/operation-handovers?taskId='+first},
            {'label':'本人完工申请及审核结果','pageUrl':'/planning/operation-completions?taskId='+first}]
    if review:
        links += [{'label':'职责范围独立完工审核记录','pageUrl':'/planning/operation-completions?taskId='+str(review[0].pk)},
            {'label':'授权整单生产完结与成品追溯','pageUrl':'/planning/finished-goods-handovers'}]
    transfers=[]
    if warehouse:
        for row in Transfer.objects.filter(company_id=actor.company_id,receiver_id=actor.pk).select_related('work_order'):
            if not warehouse_qualification(actor,required=False,purpose=row.work_order.usage_purpose)['ready']:continue
            transfers.append({'id':row.pk,'no':row.no,'workOrderId':row.work_order_id,'workOrderNo':row.work_order.no,
                'statusLabel':('成品已接收并正式用途入库' if row.work_order.usage_purpose=='PRODUCTION_USE' and row.status=='received' else {'received':'成品已接收并测试入库','prepared':'待交出','in_transit':'待本人接收入库','cancelled':'已取消'}[row.status])})
        links.append({'label':'本人指定的成品交接及测试入库','pageUrl':'/planning/finished-goods-handovers'})
    visible={t.pk:t for t in [*own,*review]}
    from .work_order_models import ProductionWorkOrder
    allowed_order_ids={t.work_order_id for t in visible.values()}|{x['workOrderId'] for x in transfers}
    orders=list(ProductionWorkOrder.objects.filter(company_id=actor.company_id,usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE'),pk__in=allowed_order_ids).select_related('source_schedule'))
    if work_order_id is not None and work_order_id not in allowed_order_ids:
        raise PlanningBusinessError('MES_ORDER_NOT_VISIBLE','所选工单不在当前公司、本人任务、独审或指定接收范围。',http_status=403)
    if work_order_id is None and not directory and len(orders)==1:work_order_id=orders[0].pk
    order=next((x for x in orders if x.pk==work_order_id),None)
    selected_order=None;actual_edges={};omissions=[]
    if order:
        from .test_work_order_service import verify
        from .finished_goods_authority import task_graph
        if order.usage_purpose=='PRODUCTION_USE':
            from .mes_native_navigation import formal_graph
            all_tasks,edges,formal_omissions=formal_graph(order)
        else:
            verify.validate_only(order)
            all_tasks,edges,_,_=task_graph(order)
        actual_edges={t.pk:[] for t in all_tasks}
        for previous,target in edges:actual_edges[target.pk].append(previous.no)
        if order.usage_purpose=='PRODUCTION_USE':
            selected_order={'id':order.pk,'no':order.no,'usagePurpose':order.usage_purpose,'productionPlanId':order.production_plan_id,
                'arrangementId':None,'arrangementRevision':None,'routingVersionId':all_tasks[0].source_operation.root_routing_version_id if all_tasks else None,
                'sourceSnapshotHash':order.snapshot_hash,'sourceLabel':'正式订单 → 发布工程／BOM／路线 → 生产计划及正式排程 → 下达及车间接收；独立开发样本不代表企业放行'}
        else:selected_order={'id':order.pk,'no':order.no,'usagePurpose':order.usage_purpose,'productionPlanId':order.production_plan_id,
            'arrangementId':order.source_snapshot['scope']['arrangementId'],'arrangementRevision':order.source_snapshot['scope']['arrangementRevision'],
            'routingVersionId':order.source_snapshot['scope']['routingVersionId'],'sourceSnapshotHash':order.snapshot_hash,
            'sourceLabel':'TEST工单 → 原订单执行安排 → 冻结路线／排程；无正式生产计划，不伪造关联'}
        visible={key:t for key,t in visible.items() if t.work_order_id==work_order_id}
        if len(visible)==len(all_tasks):
            omissions=formal_omissions if order.usage_purpose=='PRODUCTION_USE' else [{'sequence':x['sequence'],'decisionLabel':x.get('decisionLabel','条件未触发，本单不执行')} for x in order.source_snapshot['routeSelections'] if x['decision']=='NOT_APPLICABLE']
        transfers=[x for x in transfers if x['workOrderId']==work_order_id]
    elif not directory:visible={}
    from .test_workshop_task_service import verify as verify_task
    visible=dict(sorted(visible.items(),key=lambda pair:(pair[1].work_order_id,pair[1].source_operation.sequence)))
    scoped_own=sorted((x for x in own if x.pk in visible),key=lambda x:(x.work_order_id,x.source_operation.sequence))
    scoped_review=sorted((x for x in review if x.pk in visible),key=lambda x:(x.work_order_id,x.source_operation.sequence))
    links=[]
    if scoped_own:
        tid=str(scoped_own[0].pk)
        links=[{'label':'本人分次报工','pageUrl':'/planning/operation-reports?taskId='+tid},
            {'label':'部分产出确认','pageUrl':'/planning/operation-handovers?taskId='+tid+'&subview=output'},
            {'label':'本任务接收的上游交接','pageUrl':'/planning/operation-handovers?taskId='+tid+'&direction=incoming'},
            {'label':'本任务交出的下游交接','pageUrl':'/planning/operation-handovers?taskId='+tid+'&direction=outgoing'},
            {'label':'独立审核完工','pageUrl':'/planning/operation-completions?taskId='+tid}]
    if scoped_review:links.append({'label':'独立审核完工','pageUrl':'/planning/operation-completions?taskId='+str(scoped_review[0].pk)})
    if warehouse or scoped_review:links.append({'label':'成品交接入库','pageUrl':'/planning/finished-goods-handovers'+('?workOrderId='+str(order.pk) if order else '')})
    from .mes_native_navigation import dispatch_entries
    dispatch_links, dispatch_blocked = dispatch_entries(actor)
    links.extend(dispatch_links)
    if order and len({t.source_operation.sequence for t in visible.values()})!=len(visible):
        raise PlanningBusinessError('MES_FROZEN_ORDER_AMBIGUOUS','冻结执行顺位重复，不能用任务ID或编号尾号替代。',http_status=409)
    rows=[]
    from .operation_start_models import ProductionOperationStart
    from .operation_report_models import ProductionOperationReport
    from .operation_completion_generation_models import OperationCompletionGeneration
    from django.db.models import Count
    starts={x.task_id:x for x in ProductionOperationStart.objects.filter(task_id__in=visible)}
    counts={x['task_id']:x['count'] for x in ProductionOperationReport.objects.filter(task_id__in=visible).values('task_id').annotate(count=Count('id'))}
    generations={x.task_id:x for x in OperationCompletionGeneration.objects.filter(task_id__in=visible,status__in=('pending','approved')).select_related('approval_decision__actor')}
    own_ids={x.pk for x in own}
    for task in visible.values():
        verify_task.validate_only(task)
        start=starts.get(task.pk);approved=generations.get(task.pk)
        reviewer=approved.approval_decision.actor if approved and approved.approval_decision_id else None
        rows.append({'id':task.pk,'no':task.no,'workOrderNo':task.work_order.no,
            'operationName':task.source_snapshot['operation']['operationName'],
            'frozenSequence':task.source_operation.sequence,'frozenPredecessorSequences':task.source_snapshot['operation']['predecessorSequences'],
            'actualPredecessorTaskNos':actual_edges.get(task.pk) if order else None,'listSequence':len(rows)+1,
            'reviewStatusLabel':approved.get_status_display()+'（原记录；详情核验）' if approved else '尚无独审申请',
            'actualReviewerName':reviewer.real_name if reviewer else '尚未审核','actualReviewerUsername':reviewer.username if reviewer else None,
            'employeeName':task.assignment_snapshot.get('employeeName'),'plannedStart':task.source_snapshot['operation']['start'],
            'startedAt':start.started_at.isoformat() if start else None,
            'reportCount':counts.get(task.pk,0),
            'statusLabel':'已有独审完工记录（详情页核验当前证明）' if approved else '已有开工记录' if start else '待开工',
            'reportUrl':'/planning/operation-reports?taskId='+str(task.pk) if task.pk in own_ids else None,
            'reviewUrl':'/planning/operation-completions?taskId='+str(task.pk)})
    return {'factSource':'server','companyId':actor.company_id,'currentActorEvidence':{'userId':actor.pk,'username':actor.username},
        'statusLabel':'按当前有效职责读取；导航不授予写权限','scopeLabel':'本人执行及授权独审范围' if rows else '已核实本人授权任务；请选择工单或跨单目录' if own or review else '本人所属车间的正式任务准备及派工范围' if dispatch_links else '仓管仅查看本人指定成品交接及入库' if warehouse else '当前无有效MES执行、独审或成品接收职责',
        'dispatchEntries':dispatch_links,'dispatchSourceBlocks':dispatch_blocked,
        'selectionRequired':bool((own or review) and not directory and order is None),
        'selectedWorkOrder':selected_order,'directoryMode':'authorized_cross_order' if directory else 'selected_test_order',
        'workOrderOptions':[{'id':x.pk,'no':x.no} for x in orders],'omittedFrozenNodes':omissions,
        'orderRuleLabel':'列表序号仅为显示行号；工序序号沿本单冻结路线保留间隔，分支及前置不按编号推断。',
        'links':links,'tasks':rows,'transfers':transfers,'businessWriteCount':0,'auditWriteCount':0,
        'historyRule':'已完成记录继续按公司、本人关系及有效职责读取；完成不恢复报工、交接或入库操作。'}

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from django.db import DatabaseError
from workflow_runtime.fact_loads import successful_fact_load_facts, failed_fact_load_facts
from .views import envelope
from .services import PlanningBusinessError
from pde.order_routing_execution_service import ArrangementError
class MesExecutionEntryView(APIView):
    permission_classes=[IsAuthenticated]
    http_method_names=['get','head','options']
    def failure(self,code,message,status):
        load=failed_fact_load_facts(request=self.request,api_url=self.request.path,tenant_id=str(getattr(self.request.user,'company_id','')),http_status=status,error_code=code,error_message=message)
        return envelope({**load,'factLoadFacts':load,'passed':False},error={'code':code,'message':message},http_status=status)
    def handle_exception(self,error):
        if isinstance(error,APIException):return self.failure(str(error.default_code),str(error.detail),error.status_code)
        return super().handle_exception(error)
    @routing_read_request
    def get(self,request):
        try:
            if set(request.query_params)-{'workOrderId','directory'} or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):raise PlanningBusinessError('MES_ENTRY_QUERY_INVALID','职责入口仅接受明确测试工单或有权跨单目录。',http_status=400)
            raw=request.query_params.get('workOrderId');directory=request.query_params.get('directory')
            if raw is not None and (not raw.isascii() or not raw.isdigit() or raw.startswith('0') or len(raw)>18) or directory not in (None,'all') or raw and directory:raise PlanningBusinessError('MES_ENTRY_QUERY_INVALID','工单须为准确正整数；跨单目录须独立选择。',http_status=400)
            facts=read_entry(request.user,int(raw) if raw else None,directory=='all')
            load=successful_fact_load_facts(request=request,api_url=request.path,tenant_id=str(request.user.company_id),result_count=len(facts['tasks'])+len(facts['transfers']))
            return envelope({**load,'entryFacts':facts,'factLoadFacts':load})
        except PlanningBusinessError as e:
            return self.failure(e.code,e.message,e.http_status)
        except ArrangementError as e:
            return self.failure(e.code,str(e),403 if e.code=='SCOPE_DENIED' else 409)
        except DatabaseError:
            return self.failure('MES_ENTRY_READ_FAILED','当前服务端职责读取失败；未返回旧任务或空结果，请保留错误诊断。',503)
