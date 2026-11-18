"""Read-only summary of native work; no new status, ledger or execution authority.

Persisted lifecycle predicates select candidates only. Every returned current
item/action is read again through its native permission/qualification service.
Completed history is counted without loading frozen proofs or detail DTOs.
"""
import os
from django.db import transaction
from django.utils import timezone
from .operation_resource_read_scope import scoped_execution_read
from .mes_test_source_bridge import _actor, _authority, _effective
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_completion_generation_models import OperationCompletionGeneration as Generation
from workflow_runtime.models import BusinessStateTransition
from .operation_completion_contract import OBJECT
from .services import PlanningBusinessError

CONTRACT='PCE-ENTERPRISE-WORK-SUMMARY-V2'

@scoped_execution_read
@transaction.atomic
def read_summary(user):
    actor,_=_actor(user)
    from system.models import Company
    if not Company.objects.filter(pk=actor.company_id,is_active=True).exists():
        raise PlanningBusinessError("SCOPE_DENIED","公司已失效或未绑定，工作摘要不可用。",http_status=403)
    result={'contractVersion':CONTRACT,'factSource':'server','companyId':actor.company_id,
        'actorId':actor.pk,'observedAt':timezone.now().isoformat(),'environmentLabel':'独立开发测试环境' if (os.environ.get('PCE_ISOLATED_RUNSERVER_TEST')=='1') else '当前企业环境',
        'usagePurpose':'AUTHORIZED_NATIVE_PURPOSES' if (os.environ.get('PCE_ISOLATED_RUNSERVER_TEST')=='1') else None,
        'items':[],'alerts':[],'historyRecordCount':0,'businessWriteCount':0,
        'scopeLabel':'当前公司、本人执行及现有职责范围','links':[],
        'unsupportedAlertTypes':['交期与缺料预警尚无本首页权威摘要，未生成提醒'],
        'qualificationSource':'native MES read services; never status-label inference'}
    # Independent development loading is not an enterprise rollout decision.
    if not (os.environ.get('PCE_ISOLATED_RUNSERVER_TEST')=='1'):
        raise PlanningBusinessError('HOME_CAPABILITY_UNAVAILABLE','当前环境尚未接入企业工作摘要；数量不可用。',http_status=503)
    from .test_operation_start_service import _boundary
    _boundary()
    from . import test_operation_start_protocol as protocol
    from .operation_completion_v3_authority import reviewer_can_read
    from .operation_report_service import read_operation_reports
    from .operation_completion_service import read_operation_completions
    from .operation_handover_facts import read_operation_handovers
    from .finished_goods_service import read_finished_goods
    from .operation_handover_core import qualify
    from .operation_handover_contract import ACTIONS as HANDOVER_ACTIONS
    from .finished_goods_permissions import warehouse_qualification
    from .operation_handover_models import OperationHandover as Handover
    from .finished_goods_models import ProductionFinishedGoodsTransfer as Transfer
    from .operation_start_models import ProductionOperationStart

    today=timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    records=Task.objects.filter(company_id=actor.company_id,work_order__usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE')).select_related(
        'execution_employee','source_operation__work_center','workshop','work_center','work_order__source_schedule__execution_arrangement__source_calculation__sales_order_item__sales_order')
    from .mes_native_navigation import owned_tasks
    _,native_owned=owned_tasks(actor)
    own={t.pk:t for t in native_owned};review={}
    can_review=_authority(actor,'production.operation.complete.read',None,actor.pk)[0]
    for task in records:
        if task.work_order.usage_purpose=='TEST_BUSINESS' and task.execution_employee_id and task.execution_employee.user_id==actor.pk:
            if (_effective(task.work_center,today) and task.work_center.company_id==actor.company_id
                and task.work_center.workshop_id==task.workshop_id
                and protocol._qualification(actor,task,{'ready':True},{'ready':True},state='waiting')['ready']):
                own[task.pk]=task
        if can_review and reviewer_can_read(actor,task):review[task.pk]=task
    visible={**own,**review}
    result['historyRecordCount']=len(visible)
    linkset={}
    def link(label,url):linkset[url]={'label':label,'pageUrl':url}
    if own:
        link('本人报工及开工历史','/planning/operation-reports')
        link('本人交接历史','/planning/operation-handovers')
    if review:link('职责范围独立审核历史','/planning/operation-completions')
    warehouse=warehouse_qualification(actor,required=False)['ready'] or warehouse_qualification(actor,required=False,purpose='PRODUCTION_USE')['ready']
    if warehouse or review:link('成品交接及入库历史','/planning/finished-goods-handovers')
    if visible or warehouse:link('本人授权任务目录','/planning/mes-test-execution?directory=all')
    result['links']=list(linkset.values())
    # These are candidate indexes, not assertions that completion is valid or
    # that an actor may execute. Native reads below supply all action facts.
    active={x.task_id:x for x in Generation.objects.filter(company_id=actor.company_id,task_id__in=visible,status__in=('pending','approved'))}
    legacy_done=set(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id__in=visible,target_state='completed').values_list('object_id',flat=True))
    legacy_pending=set(BusinessStateTransition.objects.filter(object_type=OBJECT,object_id__in=visible,target_state='pending_review').values_list('object_id',flat=True))-legacy_done
    candidates={pk:t for pk,t in visible.items() if not (pk in active and active[pk].status=='approved') and (pk in active or pk not in legacy_done)}
    from .mes_evidence_graph import prepare_tasks
    prepare_tasks(list(candidates.values()))
    starts=set(ProductionOperationStart.objects.filter(task_id__in=own).values_list('task_id',flat=True))
    def add(kind,key,no,url,status,actions):
        # No frontend eligibility calculation. Keep action codes separate from
        # Chinese display labels, and do not count recovery/cancel as new work.
        current=[{'actionCode':a.get('actionCode') or a.get('actionId'),
            'label':a.get('displayName') or a.get('actionName') or a.get('actionLabel') or k,
            'enabled':a.get('enabled',a.get('executable',False)),
            'disabledReason':a.get('disabledReason','')} for k,a in actions.items()]
        item={'key':kind+':'+str(key),'kind':kind,'no':no,'pageUrl':url,'statusLabel':status,'actions':current}
        if kind in {'start', 'report', 'completionReplacement', 'review'}:
            task = visible[key]
            item.update(objectType='ProductionWorkshopTask', workOrderNo=task.work_order.no,
                        operationName=task.source_snapshot['operation']['operationName'])
        result['items'].append(item)
        reasons=list(dict.fromkeys(a['disabledReason'] for a in current if not a['enabled'] and a['disabledReason']))
        if reasons and not any(a['enabled'] for a in current):
            result['alerts'].append({'objectNo':no,'reason':'；'.join(reasons),'pageUrl':url,'source':'native disabledReason'})
    def read_item(kind,key,no,url,reader,project):
        try:project(reader())
        except PlanningBusinessError as e:
            if e.http_status==403 and e.code in {'OPERATION_REPORT_READ_DENIED','OPERATION_REPORT_TASK_NOT_VISIBLE','OPERATION_COMPLETION_READ_DENIED','OPERATION_COMPLETION_TASK_NOT_VISIBLE','HANDOVER_READ_DENIED','HANDOVER_NOT_VISIBLE','FG_READ_DENIED','FG_TRANSFER_NOT_VISIBLE'}:return
            # Source inconsistency must not become an empty/zero work summary.
            raise
    for pk,task in candidates.items():
        if pk in own and pk not in starts:
            if task.work_order.usage_purpose=='PRODUCTION_USE':
                from .operation_start_service import read_operation_starts as read_starts
            else:
                from .test_operation_start_service import read as read_starts
            def project_start(f,t=task):
                row=next(r for r in f.get('tasks',f.get('rows',[])) if r['taskId']==t.pk)
                add('start',t.pk,t.no,'/planning/operation-starts?taskId='+str(t.pk) if t.work_order.usage_purpose=='PRODUCTION_USE' else '/planning/mes-test-execution?workOrderId='+str(t.work_order_id),row['statusLabel'],{'start':row.get('availableActions',{}).get('start',row.get('availableAction'))})
            read_item('start',pk,task.no,'',lambda t=task:read_starts(user=actor,task_id=t.pk) if t.work_order.usage_purpose=='PRODUCTION_USE' else read_starts(user=actor,work_order_id=t.work_order_id,own_only=True),project_start)
        elif pk in own and pk in starts and pk not in active and pk not in legacy_pending:
            def project_report(f,t=task):
                row=f['selectedTask']
                if not any(a['enabled'] for a in row['availableActions'].values()):
                    complete=read_operation_completions(user=actor,task_id=t.pk)['selectedTask']
                    row['availableActions']['completionRequest']=complete['availableActions']['request']
                add('report',t.pk,t.no,'/planning/operation-reports?taskId='+str(t.pk),row['statusLabel'],row['availableActions'])
            read_item('report',pk,task.no,'',lambda pk=pk:read_operation_reports(user=actor,task_id=pk),project_report)
        if pk in own and pk in active and active[pk].status=='pending':
            def project_replace(f,t=task):
                row=f['selectedTask'];action=row['availableActions'].get('withdrawReplace')
                if action and action['enabled']:
                    add('completionReplacement',t.pk,t.no,'/planning/operation-completions?taskId='+str(t.pk),row['completionStatusLabel'],{'withdrawReplace':action})
            read_item('completionReplacement',pk,task.no,'',lambda pk=pk:read_operation_completions(user=actor,task_id=pk),project_replace)
        if pk in review and (pk in legacy_pending or pk in active and active[pk].status=='pending'):
            def project_review(f,t=task):
                row=f['selectedTask'];add('review',t.pk,t.no,'/planning/operation-completions?taskId='+str(t.pk),row['completionStatusLabel'],{'approve':row['availableActions']['approve']})
            read_item('review',pk,task.no,'',lambda pk=pk:read_operation_completions(user=actor,task_id=pk),project_review)
    for h in Handover.objects.filter(company_id=actor.company_id,status__in=('prepared','in_transit','partially_received','discrepancy_pending')).select_related('source_work_center','target_work_center'):
        duty='dispatch' if h.status=='prepared' else 'receive'
        duty_wc=h.source_work_center_id if duty=='dispatch' else h.target_work_center_id
        if not qualify(actor,HANDOVER_ACTIONS[duty][0],duty_wc,'OperationHandover',h.pk,status=h.status,required=False)['ready']:continue
        if not any(qualify(actor,HANDOVER_ACTIONS['read'][0],wc,'OperationHandover',h.pk,required=False)['ready'] for wc in (h.source_work_center_id,h.target_work_center_id)):continue
        def project_handover(f,h=h,duty=duty):
            add('handover',h.pk,h.no,'/planning/operation-handovers?handoverId='+str(h.pk),f['selectedHandover']['statusLabel'],{k:a for k,a in f['availableActions'].items() if k in ('dispatch','receive')})
            result['items'][-1]['currentDuty']=duty
        read_item('handover',h.pk,h.no,'',lambda h=h:read_operation_handovers(user=actor,handover_id=h.pk),project_handover)
    for transfer in Transfer.objects.filter(company_id=actor.company_id,status__in=('prepared','in_transit')).select_related('task__workshop'):
        if not (transfer.status=='prepared' and transfer.created_by_id==actor.pk or transfer.status=='in_transit' and transfer.receiver_id==actor.pk):continue
        from .finished_goods_permissions import source_qualification
        duty_q=warehouse_qualification(actor,transfer.pk,transfer.status,required=False,purpose=transfer.work_order.usage_purpose) if transfer.status=='in_transit' else source_qualification(actor,'dispatch',transfer.task,transfer.pk,transfer.status,required=False)
        if not duty_q['ready']:continue
        def project_fg(f,t=transfer):
            add('finishedGoods',t.pk,t.no,'/planning/finished-goods-handovers?transferId='+str(t.pk),f['selectedTransfer']['statusLabel'],{k:a for k,a in f['availableActions'].items() if k in ('dispatch','receive')})
            native = f['selectedTransfer']
            result['items'][-1].update(objectType='ProductionFinishedGoodsTransfer',
                workOrderNo=native['workOrderNo'], productName=native['productName'])
        read_item('finishedGoods',transfer.pk,transfer.no,'',lambda t=transfer:read_finished_goods(user=actor,transfer_id=t.pk),project_fg)
    result['total']=len(result['items'])
    result['executableActionCount']=sum(a['enabled'] for row in result['items'] for a in row['actions'])
    result['activeOwnTaskCount']=len(set(candidates)&set(own)&starts)
    from .enterprise_home_projection import role_groups
    result['roleGroups']=role_groups(actor,result,own,review,can_review,warehouse)
    result['rolePresentationContract']='PCE-ROLE-HOME-20261115-B3-R1'
    result['combinedRoleTotalSupported']=False
    return result
