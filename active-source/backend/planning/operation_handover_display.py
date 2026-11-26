"""Read-only labels over native historical events and current formal route facts.

No target, party, quantity, eligibility or historical snapshot is changed.
"""
from .services import PlanningBusinessError

CONTRACT='PCE-HANDOVER-DIRECTION-DISPLAY-V1'
TITLE='工艺适用与后序依据'


def direction_display(header,route,*,error=None):
    source=header['sourceOperationName']
    historical={'title':'本张历史交接（当时记录）',
        'processLabel':source+'→'+header['targetOperationName'],
        'workCenterLabel':header['sourceWorkCenterName']+'→'+header['targetWorkCenterName']}
    current={'title':'当前正式工艺','readStatus':'read_failed' if error else 'pending',
        'processLabel':'当前正式后序尚未核实','workCenterLabel':'当前正式路线资源尚未核实',
        'nextExecutionOperations':None,'waiting':[], 'explanation':str(error.message) if error else '正式路线来源尚未核实，请重新读取；不能按历史目标推定当前后序。'}
    conflict=bool(header.get('routeSourceConflicts'))
    if route is not None and route['sourceStatus']=='VALID' and not route['unresolvedSuccessors']:
        next_rows=route['nextExecutionOperations'];current['readStatus']='loaded'
        current['nextExecutionOperations']=[{'operationId':r['operationId'],'operationName':r['operationName'],
            'workCenterNames':r['capacitySource'].get('workCenterNames',[]),
            'quantityMode':r['quantityMode']} for r in next_rows]
        current['processLabel']=source+'→'+('、'.join(r['operationName'] for r in next_rows) if next_rows else '无后续执行工序')
        own=next((r for r in route['operations'] if r['sequence']==route['sourceOperationSequence']),None)
        own_centers=(own or {}).get('capacitySource',{}).get('workCenterNames',[])
        next_centers=list(dict.fromkeys(n for r in next_rows for n in r['capacitySource'].get('workCenterNames',[])))
        current['workCenterLabel']=('、'.join(own_centers) or '来源路线资源待核实')+'→'+('、'.join(next_centers) if next_centers else '无后续路线资源' if not next_rows else '后序路线资源待核实')
        current['explanation']=('这张历史交接当时记录为“'+historical['processLabel']+'”，与已核实的当前正式工艺“'+current['processLabel']+'”不一致。原记录保留用于追溯，不能作为当前后序已接收的凭证。' if conflict else '上方历史去向保留本张交接当时的记录；当前正式工艺单独显示下一道实际执行工序。非量工序仍须完成，实物接收点可能位于其后。')
        for row in next_rows:
            if row.get('productionPlanningStatus')=='AWAITING_ACTUAL_RECEIPT':
                name=row['operationName']
                current['waiting'].append({'operationId':row['operationId'],'operationName':name,
                    'title':name+'为什么还在等待',
                    'missing':'目前缺少本工单交到'+name+'的有效实收批次和数量。',
                    'impact':'取得这项投入依据前，'+name+'的新任务派工、开工和报工继续等待。',
                    'history':'这张旧交接单按当时去向保留；查看、刷新或重复办理原单不会把它变成'+name+'的实收凭证。无需为消除等待提示重办原交接。'})
    elif error is not None:current['errorCode']=error.code
    return {'contractVersion':CONTRACT,'routeSectionTitle':TITLE,'historical':historical,
        'current':current,'historicalConflict':conflict,'originalHistoryPreserved':True,
        'businessWriteCount':0}


def decorate_directions(actor,headers,*,known_routes=None):
    from .operation_route_facts import read_operation_route
    from .workshop_task_models import ProductionWorkshopTask
    routes=dict(known_routes or {})
    for header in headers:
        key=header['taskId'];error=None
        if key not in routes:
            source=ProductionWorkshopTask.objects.select_related('work_order','source_operation','work_center').get(pk=key,company_id=actor.company_id)
            try:routes[key]=read_operation_route(source,actor,verified_headers=headers)
            except PlanningBusinessError as exc:routes[key]=exc
        route=routes[key]
        if isinstance(route,PlanningBusinessError):error=route;route=None
        header['directionDisplay']=direction_display(header,route,error=error)
    return headers
