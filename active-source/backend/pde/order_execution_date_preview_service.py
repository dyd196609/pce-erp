"""Read-only TEST arrangement adapter to the delivered native minute engine.

No formal plan, policy revision, resource reservation or alternative scheduler.
The accepted test Shift is the explicit calendar authority for this context;
confirmed historical capacity policies are evidence of phase semantics only.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from zoneinfo import ZoneInfo
from django.db import connection, transaction
from pfm.models import Shift
from .models import WorkCenter, RoutingStep, StandardCapacity
from .order_execution_capacity_read_service import read_capacity_review
from .order_execution_workload_read_service import fail
from .manufacturing_shift_calendar import validate_shift_calendar, DAYS
from .manufacturing_time_calculation import resolve_time_window, preview_operation_time, CONTRACT as ENGINE
from .routing_planning_readiness_service import RoutingPlanningReadinessService as Rules

CONTRACT = 'PCE-ORDER-TEST-DATE-PREVIEW-V1'
TEST_BASIS = '本轮日期预览测试输入：已验收数量/天产能按已保存测试班次净工作分钟线性换算；不是实测产能或正式制度修订'

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

def _resources(company_id):
    # The isolation checkout predates these existing tables. Read their native
    # persisted authority directly, never fabricate missing ORM records.
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM pde_manufacturing_time_policy_revision WHERE company_id=%s AND kind='OPERATION_RESTRICTION' AND status='confirmed'", [company_id])
        if cursor.fetchone()[0]:
            fail('OPERATION_RESTRICTION_ADAPTER_REQUIRED', '存在已确认工序时间限制，须先解析适用范围；不忽略限制计算')
        cursor.execute('SELECT r.id,r.work_center_id,r.start_at,r.end_at,r.production_date,r.minutes,r.schedule_id,s.company_id,s.status,s.usage_purpose FROM planning_processing_reservation r LEFT JOIN planning_formal_production_schedule s ON s.id=r.schedule_id WHERE r.company_id=%s AND r.released_at IS NULL ORDER BY r.id', [company_id])
        occupied = [dict(zip([x[0] for x in cursor.description], row)) for row in cursor.fetchall()]
        cursor.execute("SELECT id,payload,content_hash FROM pde_manufacturing_time_policy_revision WHERE company_id=%s AND kind='CAPACITY_TIME_BASIS' AND status='confirmed' ORDER BY id", [company_id])
        policies = [dict(zip([x[0] for x in cursor.description], row)) for row in cursor.fetchall()]
    if not policies:
        fail('PHASE_SEMANTICS_MISSING', '既有阶段占用语义缺少可追溯依据')
    semantics = []
    for policy in policies:
        payload = json.loads(policy['payload']) if isinstance(policy['payload'], str) else policy['payload']
        semantics.append({name: {key: payload[name].get(key) for key in ('clock','unit','occupancy','interruptible','parallel')} for name in ('preparation','transfer')})
    if len({digest(x) for x in semantics}) != 1:
        fail('PHASE_SEMANTICS_AMBIGUOUS', '既有阶段规则不一致，不能自动选择测试占用方式')
    expected = {'clock':'STANDARD_CAPACITY_DAY','unit':'DAY','occupancy':'WORK_TIME_ONLY','interruptible':True,'parallel':False}
    if any(semantics[0][name] != expected for name in ('preparation','transfer')):
        fail('PHASE_SEMANTICS_UNSUPPORTED', '测试适配尚未承接此阶段时钟或占用规则')
    bookings = {}
    verified_test=set()
    for row in occupied:
        if row['company_id'] != company_id or row['status'] != 'saved':
            fail('RESERVATION_STATE_UNPROVEN', '未释放占用的公司或排程状态不一致')
        if row['usage_purpose'] not in ('PRODUCTION_USE','TEST_BUSINESS'):
            fail('RESERVATION_PURPOSE_UNPROVEN','未分类排程占用拒绝承接。')
        if row['usage_purpose']=='TEST_BUSINESS' and row['schedule_id'] not in verified_test:
            from planning.test_scheduling_service import verify
            from planning.models import FormalProductionSchedule
            verify(FormalProductionSchedule.objects.get(pk=row['schedule_id']))
            verified_test.add(row['schedule_id'])
        elif row['usage_purpose']=='PRODUCTION_USE' and row['schedule_id'] not in verified_test:
            from planning.formal_scheduling_service import _verify_schedule
            from planning.models import FormalProductionSchedule
            _verify_schedule(FormalProductionSchedule.objects.get(pk=row['schedule_id']))
            verified_test.add(row['schedule_id'])
        def instant(value):
            value = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        start, end = instant(row['start_at']), instant(row['end_at'])
        if end <= start or abs(Decimal(str(row['minutes'])) - Decimal(str((end-start).total_seconds()))/60) > Decimal('.00001'):
            fail('RESERVATION_INTERVAL_INVALID', '既有占用时段与保存分钟不一致')
        bookings.setdefault(f"{company_id}:{row['work_center_id']}", []).append({'start':start.isoformat(), 'end':end.isoformat(), 'productionDate':str(row['production_date']), 'sourcePaths':[f"planning_processing_reservation:{row['id']}/schedule:{row['schedule_id']}"]})
    return bookings, {'activeReservationCount':len(occupied), 'reservationSource':'planning_processing_reservation / planning_formal_production_schedule（未释放、saved、同公司）', 'reservationHash':digest(occupied), 'phasePolicyIds':[x['id'] for x in policies], 'phasePolicyHashes':[x['content_hash'] for x in policies], 'phaseSemantics':semantics[0], 'phaseScopeLabel':'原制度仅证明既有阶段语义；不宣称其产能适用范围覆盖当前产能。当前使用本轮独立测试消费上下文。'}

def _calendar(center):
    calendar = center.capacity_policy.get('calendar', {})
    source = validate_shift_calendar(work_center=center, calendar=calendar)
    if not source or calendar.get('timezone') != 'Asia/Shanghai':
        fail('TEST_CALENDAR_REQUIRED', '缺少已核验的测试班次日历')
    # Refuse an unimplemented exception conversion rather than silently omit it.
    if calendar.get('exceptions'):
        fail('TEST_CALENDAR_EXCEPTION_ADAPTER_REQUIRED', '此班次已有例外日，须先承接准确时段；不能只按分钟猜测')
    shift = Shift.objects.get(pk=source['shiftId'], company_id=center.company_id)
    def segment(left, right):
        offset = int(right <= left)
        return {'start':left.strftime('%H:%M'), 'end':right.strftime('%H:%M'), 'startDayOffset':0, 'endDayOffset':offset}
    span = {'inputMode':'WINDOWS_WITH_BREAKS', 'segments':[segment(shift.start_time, shift.end_time)], 'breaks':[]}
    if shift.break_start:
        item = segment(shift.break_start, shift.break_end)
        item['startDayOffset'] = int(shift.break_start < shift.start_time)
        item['endDayOffset'] += item['startDayOffset']
        span['breaks'] = [item]
    shared = {'timezone':calendar['timezone'], 'patterns':{'TEST_SHIFT':{'processing':span, 'resource':deepcopy(span)}}, 'weeklyPatterns':{d:'TEST_SHIFT' if d in source['workingWeekdays'] else None for d in DAYS}, 'exceptions':[]}
    return shared, source

@transaction.atomic
def preview_dates(*, user, arrangement_id, start_at, use_saved_context=True):
    review = read_capacity_review(user=user, arrangement_id=arrangement_id)
    try:
        start = datetime.fromisoformat(start_at)
        if start.tzinfo is None or start.utcoffset() != timedelta(hours=8):
            raise ValueError()
        start = start.astimezone(ZoneInfo('Asia/Shanghai'))
    except (ValueError, TypeError):
        fail('TEST_START_INVALID', '测试开始时间须包含北京时间+08:00时区')
    if review['summary']['calculatedCount'] != review['summary']['requiredCount'] or not review['summary']['workloadReady']:
        fail('DATE_INPUT_INCOMPLETE', '当前有效需求或产能仍有缺项，请先查看产能与日历核对')
    company = user.company_id
    bookings, resource_facts = _resources(company)
    if use_saved_context:
        from planning.models import FormalProductionSchedule
        from planning.test_scheduling_service import verify,source_signature,read
        saved=FormalProductionSchedule.objects.filter(company_id=company,execution_arrangement_id=arrangement_id,usage_purpose='TEST_BUSINESS',status='saved').first()
        if saved:
            verify(saved)
            if saved.snapshot['sourceSignature']==source_signature(review) and saved.snapshot['preview']['testStartAt']==start.isoformat():
                value=deepcopy(saved.snapshot['preview'])
                from .test_schedule_storage_support import inspect_storage
                value['saveSupport']=inspect_storage(company)
                value.update(savedContextRead=True,resourceReservationSaved=True,savedScheduleId=saved.pk,currentResourceFacts=resource_facts,scheduleFacts=read(user=user,arrangement_id=arrangement_id,current_review=review),statusLabel='已保存测试日期独立回读；来源已重新核验，不重复预占资源')
                value['admissionToken']=saved.admission_token
                value['previewHash']=digest(value)
                return value
    original_bookings = deepcopy(bookings)
    fixed = RoutingStep.objects.in_bulk([r['stepId'] for r in review['rows']])
    pending = {r['sequence']:deepcopy(r) for r in review['rows']}
    finished = {}
    while pending:
        for row in pending.values():
            predecessors = fixed[row['stepId']].predecessor_sequences or []
            if any(type(p) is not int or p >= row['sequence'] or p not in pending and p not in finished for p in predecessors):
                fail('ROUTING_DEPENDENCY_INVALID', '固定路线前置步骤不存在或顺序无效')
        eligible = [r for r in pending.values() if all(p in finished for p in fixed[r['stepId']].predecessor_sequences or [])]
        if not eligible:
            fail('ROUTING_DEPENDENCY_CYCLE', '固定路线存在循环或缺失依赖')
        row = min(eligible, key=lambda r:r['sequence'])
        predecessors = fixed[row['stepId']].predecessor_sequences or []
        earliest = max([start] + [datetime.fromisoformat(finished[p]['end']) for p in predecessors])
        row['predecessorSequences'] = predecessors
        if row['decision'] == 'NOT_APPLICABLE':
            row.update(start=earliest.isoformat(), end=earliest.isoformat(), phases=[], statusLabel='依已保存安排跳过；仅传递前置完成时点')
        elif row['decision'] != 'REQUIRED':
            fail('EXECUTION_PENDING', '执行选择待核定，不自动跳过')
        else:
            if not row['calendar']['ready']:
                fail('DATE_CALENDAR_UNAVAILABLE', row['calendar']['statusLabel'])
            center = WorkCenter.objects.get(pk=row['workCenterId'], company_id=company)
            cap = StandardCapacity.objects.select_related('operation','product_type','uom').get(pk=row['capacity']['id'], company_id=company)
            if cap.resource_scope != 'work_center' or cap.equipment_id is not None:
                fail('DATE_RESOURCE_SCOPE_UNSUPPORTED', '当前适配只承接实际工作中心资源；不假定设备或人员无限可用')
            shared, source = _calendar(center)
            minutes = source['dailyAvailableMinutes']
            basis = {'standardDaySource':'WORK_SYSTEM_REVISION', 'standardPattern':'TEST_SHIFT', 'conversionMode':'LINEAR_NET_MINUTES', 'linearApproved':True, 'processing':{'interruptible':True,'overtimeAllowed':False}, 'standardCapacityHash':digest(row['capacity']), 'businessBasis':TEST_BASIS, 'approvalBasis':'本轮用户日期排产预览隔离测试指令；只读测试、不形成正式制度批准', 'applicability':{'usagePurpose':'TEST_BUSINESS', **review['scope'], 'standardCapacityId':cap.pk,'testCalendarHash':source['sourceHash']}}
            for name, key in (('preparation','preparationDays'),('transfer','transferDays')):
                basis[name] = {**resource_facts['phaseSemantics'][name], 'value':row['result'][key], 'standardDayMinutes':str(minutes), 'basisReference':f"{row[name+'Source']} + 已保存测试班次:{source['shiftId']} / {source['sourceHash']}"}
            window = resolve_time_window(shared, start_date=start.date().isoformat(), end_date=(start.date()+timedelta(days=366)).isoformat(), company_id=company, work_center_id=center.pk)
            value = preview_operation_time(window, demand_quantity=row['workloadQuantity'], capacity_quantity=cap.quantity, basis=basis, standard_day_minutes=minutes, not_before=earliest.isoformat(), company_id=company, work_center_id=center.pk, bookings=bookings)
            if not value['ready']:
                fail('DATE_ENGINE_BLOCKED', '分钟引擎拒绝本步：'+json.dumps(value['errors'],ensure_ascii=False))
            end_date = datetime.fromisoformat(value['end']).date()
            for target in (cap,center,cap.operation,cap.product_type):
                if not Rules._active_on(target,start.date()) or not Rules._active_on(target,end_date):
                    fail('DATE_SOURCE_EXPIRED', '产能、工序、工作中心或产品范围不覆盖预览日期')
            bookings = value.pop('bookings')
            row.update(start=value['start'],end=value['end'],phases=value['phases'],processingMinutes=value['processingMinutes'],standardDayMinutes=minutes,calendarSource=source,basis=basis,statusLabel='测试日期预览完成；未预占资源')
        finished[row['sequence']] = row
        del pending[row['sequence']]
    rows = [finished[k] for k in sorted(finished)]
    end = max(datetime.fromisoformat(r['end']) for r in rows)
    resource_facts['overlappingHorizonCount'] = sum(datetime.fromisoformat(r['start']) < end and datetime.fromisoformat(r['end']) > start for group in original_bookings.values() for r in group)
    resource_facts['consideredLabel'] = '实际工作中心单资源互斥、已有未释放加工占用、工作窗口、午休、下班、周末、固定前置依赖；准备/转运按工作时间推进且不独占；未推定设备、人员或多机并行能力'
    result = {'contractVersion':CONTRACT,'engineContract':ENGINE,'factSource':'server','scope':review['scope'],'sourceIdentity':review['sourceIdentity'],'requestIdentity':review['requestIdentity'],'testStartAt':start.isoformat(),'testInputLabel':'本轮补拟测试开始时间，不是承诺生产日期','timezone':'Asia/Shanghai','rows':rows,'completionAt':end.isoformat(),'resourceFacts':resource_facts,'summary':{'previewedCount':sum(r['decision']=='REQUIRED' for r in rows),'skippedCount':sum(r['decision']=='NOT_APPLICABLE' for r in rows),'unknownCount':0},'formalManufacturingEligible':False,'resourceReservationSaved':False,'databaseBusinessWriteCount':0,'ready':True,'statusLabel':'只读测试日期预览完成；未创建正式计划、资源预占或工单'}
    from .test_schedule_storage_support import inspect_storage
    result['saveSupport'] = inspect_storage(company)
    from planning.test_scheduling_service import admission,read
    result['admissionToken']=admission(result)
    result['scheduleFacts']=read(user=user,arrangement_id=arrangement_id,current_review=review)
    result['previewHash'] = digest(result)
    return result
