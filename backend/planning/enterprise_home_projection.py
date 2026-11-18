"""Presentation of existing authorized native reads, never execution authority.

Counts use the complete service result, before UI pagination. Different object
families and overlapping duties remain separate; no combined four-role total.
"""
from django.db import DatabaseError
from .services import PlanningBusinessError
from pde.order_routing_execution_service import ArrangementError
from pde.plan_step_context_service import PlanStepContextError

READ_ERRORS = (PlanningBusinessError, ArrangementError, PlanStepContextError, DatabaseError)


def failure(group, error):
    status = getattr(error, 'http_status', 503)
    group.update(loadStatus='permission_denied' if status == 403 else 'read_failed',
                 message=getattr(error, 'message', str(error)), total=None,
                 recordCount=None, todos=[], records=[], metrics=[])


def role_groups(actor, summary, own, review, can_review, warehouse):
    from .mes_execution_entry import read_entry
    from .finished_goods_service import read_finished_goods
    from .workshop_task_service import read_workshop_tasks
    groups = []

    def group(key, label, scope, allowed, kinds):
        items = [dict(x) for x in summary['items'] if x['kind'] in kinds]
        for x in items:
            x.update(id=x['key'], contextLabel='原办理页重新核对资格',
                     reason='；'.join(dict.fromkeys(a['disabledReason'] for a in x['actions']
                                                   if not a['enabled'] and a['disabledReason'])))
        value = dict(key=key, label=label, scopeLabel=scope,
                     loadStatus=('loaded' if items else 'empty_valid') if allowed else 'permission_denied',
                     message='' if allowed else '当前账号没有该岗位已核实的读取范围；不显示为零事项。',
                     total=len(items) if allowed else None, todos=items, records=[],
                     recordCount=None, metrics=[], links=[], partial=False)
        groups.append(value)
        return value

    production = group('production', '生产员工', '本人获派任务；工序任务与交接单分别统计',
                       bool(own), {'start', 'report', 'completionReplacement'})
    reviewer = group('reviewer', '独审人员', '当前公司及原独立审核职责范围',
                     bool(review), {'review'})
    workshop = group('workshop', '车间负责人', '原车间任务服务授权范围', False, set())
    receiving = group('warehouse', '仓管人员', '仅本人被指定的成品接收单；不授予额外执行权', warehouse, set())

    if own or review:
        try:
            entry = read_entry(actor, directory=True)
            for key, target, ids, url_key in [('production', production, set(own), 'reportUrl'),
                                              ('reviewer', reviewer, set(review), 'reviewUrl')]:
                target['records'] = [dict(id=str(r['id']), no=r['no'], statusLabel=r['statusLabel'],
                    objectType='ProductionWorkshopTask', workOrderNo=r['workOrderNo'], operationName=r['operationName'],
                    contextLabel=r['workOrderNo']+' · '+r['operationName'],
                    pageUrl=r[url_key], reason='原记录仅供回查，不计入待办')
                    for r in entry['tasks'] if r['id'] in ids and r.get(url_key)]
                target['recordCount'] = len(target['records']) if target['loadStatus'] != 'permission_denied' else None
            production['metrics'] = [
                {'label': '待开工任务', 'value': sum(x['kind'] == 'start' for x in production['todos']), 'unit': '项'},
                {'label': '进行中任务', 'value': summary['activeOwnTaskCount'], 'unit': '项'},
                {'label': '待报工／实际经过核对', 'value': sum(x['kind'] == 'report' for x in production['todos']), 'unit': '项'}] if own else []
            handovers = [x for x in summary['items'] if x['kind'] == 'handover']
            if own:
                production['links'] = [{'label': '本人产出与交接记录', 'pageUrl': '/planning/operation-handovers'}]
                production['metrics'].append({'label': '职责内工序交接单', 'value': len(handovers), 'unit': '单'})
                production['metrics'].append({'label': '待交出（已备交单）', 'value': sum(x.get('currentDuty')=='dispatch' for x in handovers), 'unit': '单'})
                production.update(partial=True,message='已备交交接单按原职责统计；尚未备交产出的待交出汇总尚无权威合同，未计为0。')
                # Handover documents are not task counts and retain their own rows.
                production['relatedTodos'] = [dict(x, id=x['key'], contextLabel='工序交接单',
                    reason='；'.join(dict.fromkeys(a['disabledReason'] for a in x['actions'] if not a['enabled'] and a['disabledReason']))) for x in handovers]
            reviewer['metrics'] = [{'label': '待独审申请', 'value': reviewer['total'], 'unit': '项'},
                {'label': '当前可审核', 'value': sum(any(a['enabled'] for a in x['actions']) for x in reviewer['todos']), 'unit': '项'}] if can_review or review else []
        except READ_ERRORS as error:
            # A failed native directory is unknown, never a valid empty group.
            for target in (production, reviewer):
                if target['loadStatus'] != 'permission_denied': failure(target, error)

    try:
        facts = read_workshop_tasks(user=actor)
        workshop.update(loadStatus='service_unavailable', partial=True,
            message='车间任务及原人员安排入口已接入；完整车间待办、阻断汇总合同尚未提供，待办数量未知。',
            recordCount=len(facts['tasks']), total=None)
        by_operation = {r['id']: r for r in facts['operationOptions']}
        workshop['records'] = [dict(id=str(r['id']), no=r['no'], statusLabel=r['statusLabel'],
            objectType='ProductionWorkshopTask', workOrderNo=r.get('workOrderNo'), operationName=r.get('operationName'),
            contextLabel=r.get('workOrderNo', '')+' · '+r.get('operationName', ''),
            reason='；'.join(dict.fromkeys(by_operation.get(r['operationId'], {}).get('resourceSource', {}).get('blockingReasons', []))),
            pageUrl='/planning/workshop-tasks?workOrderId='+str(r['workOrderId'])+'&operationId='+str(r['operationId'])) for r in facts['tasks']]
        workshop['links'] = [{'label': '原车间任务与人员安排', 'pageUrl': '/planning/workshop-tasks'}]
        workshop['metrics'] = [{'label': '授权车间任务记录', 'value': len(facts['tasks']), 'unit': '条'},
            {'label': '完整车间待办', 'value': None, 'unit': '项'}]
    except READ_ERRORS as error:
        failure(workshop, error)

    if warehouse:
        try:
            facts = read_finished_goods(user=actor)
            from .finished_goods_models import ProductionFinishedGoodsTransfer
            assigned = set(ProductionFinishedGoodsTransfer.objects.filter(company_id=actor.company_id,
                           receiver_id=actor.pk).values_list('pk', flat=True))
            records = [r for r in facts['transfers'] if r['id'] in assigned]
            receiving['records'] = [dict(id=str(r['id']), no=r['no'], statusLabel=r['statusLabel'],
                objectType='ProductionFinishedGoodsTransfer', workOrderNo=r['workOrderNo'], productName=r['productName'],
                contextLabel=r['workOrderNo']+' · '+r['productName']+' · '+str(r['quantity'])+' '+r['uomLabel'],
                pageUrl='/planning/finished-goods-handovers?transferId='+str(r['id']), reason='') for r in records]
            receiving['recordCount'] = len(records)
            for r, row in zip(records, receiving['records']):
                if r['statusCode'] != 'in_transit': continue
                native = read_finished_goods(user=actor, transfer_id=r['id'])
                action = native['availableActions']['receive']
                receiving['todos'].append(dict(row, actions=[dict(action, label=action['displayName'])],
                                                reason=action['disabledReason']))
            receiving.update(total=len(receiving['todos']), loadStatus='loaded' if receiving['todos'] else 'empty_valid')
            receiving['metrics'] = [{'label': '待本人接收', 'value': receiving['total'], 'unit': '单'},
                {'label': '当前可接收并入库', 'value': sum(any(a['enabled'] for a in x['actions']) for x in receiving['todos']), 'unit': '单'}]
            receiving['message'] = '当前成品服务未提供独立差异待办合同；差异数量未知，原追溯与办理条件保留。'
            receiving['partial'] = True
        except READ_ERRORS as error: failure(receiving, error)
    for g in groups:
        g.setdefault('relatedTodos', [])
        for row in g['todos'] + g['records'] + g['relatedTodos']:
            # No independent work-order name exists. Missing native product or
            # operation names are explicit nulls, not parsed context prose.
            for field in ('workOrderNo', 'workOrderName', 'operationName', 'productName'):
                row.setdefault(field, None)
            row['contextFieldStatus'] = {
                field: 'PROVIDED' if row[field] is not None else 'NOT_PROVIDED'
                for field in ('workOrderNo', 'workOrderName', 'operationName', 'productName')
            }
        g['countBasis'] = '服务端完整授权结果去重计数；未按前端分页、数量余额或显示文案推断资格。'
    return groups
