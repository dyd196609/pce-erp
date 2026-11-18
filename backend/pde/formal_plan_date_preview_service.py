

# Native formal date consumer restoration.
from copy import deepcopy

from datetime import date, datetime, time, timedelta

from decimal import Decimal

from hashlib import sha256

import json

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction

from django.utils import timezone as django_timezone

from .daily_capacity_service import (
    AllocatedLoadCapacityReadinessService, DailyCapacityError,
    DailyCapacityReadinessService, _plan_capacity_context, _current_plan_capacity,
)

from .daily_capacity_views import validate_capability_window

from .manufacturing_time_calculation import normalize_policy_payload, preview_operation_time, resolve_time_window

from .manufacturing_time_zone_catalog import display_timezone_label

from . import manufacturing_time_policy_service as policies

from .models import ManufacturingTimePolicyRevision as Policy

from .operation_requirement_service import _source_read_cache

CONTRACT = 'PCE-EFFECTIVE-STEP-WORK-TIME-DATE-PREVIEW-V1'

CONSUMPTION_CONTRACT = 'PCE-PLAN-STEP-READONLY-DATE-CONSUMPTION-V1'

def _error(code, label):
    raise DailyCapacityError(code, label)

def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), default=str).encode('utf-8')).hexdigest()

def validate_date_consumption(basis, reference, *, exact_scope, on_date):
    """A new audited policy may consume, but never rewrite, the old proof."""
    declaration = basis['payload'].get('applicability', {}).get('datePreviewConsumption')
    keys = {'contractVersion', 'consumer', 'exactScope', 'prerequisite', 'effectiveFrom',
        'effectiveTo', 'grantsScheduling', 'grantsResourceOccupation'}
    if (not isinstance(declaration, dict) or set(declaration) != keys
            or declaration.get('contractVersion') != CONSUMPTION_CONTRACT
            or declaration.get('consumer') != 'PLAN_STEP_READONLY_DATE_PREVIEW'
            or declaration.get('exactScope') != exact_scope
            or declaration.get('grantsScheduling') is not False
            or declaration.get('grantsResourceOccupation') is not False
            or reference is None or reference.get('formalConsumptionValidated') is not True
            or reference.get('consumer') != 'ALLOCATED_LOAD_NO_DATE'
            or reference.get('exactScope') != exact_scope):
        _error('PLAN_DATE_CONSUMPTION_SCOPE_REQUIRED', '日期预览缺少本步骤精确范围的新生效只读消费用途证明')
    previous = declaration.get('prerequisite')
    expected = {key: deepcopy(reference[key]) for key in ('recordId', 'revision', 'referenceHash')}
    if isinstance(previous, dict) and 'auditIds' in previous:
        expected['auditIds'] = reference['auditIds']
    if previous != expected:
        _error('PLAN_DATE_CONSUMPTION_PREREQUISITE_CHANGED', '日期用途引用的原无日期消费修订、Hash或审计与本次正式核验不一致')
    try:
        start = date.fromisoformat(declaration['effectiveFrom'])
        end = date.fromisoformat(declaration['effectiveTo']) if declaration['effectiveTo'] else None
        basis_start = date.fromisoformat(basis['effectiveFrom'])
        basis_end = date.fromisoformat(basis['effectiveTo']) if basis['effectiveTo'] else None
        reference_start = date.fromisoformat(reference['effectiveFrom'])
        reference_end = date.fromisoformat(reference['effectiveTo']) if reference['effectiveTo'] else None
    except (TypeError, ValueError):
        _error('PLAN_DATE_CONSUMPTION_PERIOD_INVALID', '只读日期用途缺少有效的明确生效区间')
    if (on_date < start or start < basis_start or end and end < start
            or end and basis_end and end > basis_end
            or on_date < reference_start or reference_end and on_date > reference_end
            or basis_end and on_date > basis_end or end and on_date > end):
        _error('PLAN_DATE_CONSUMPTION_INACTIVE', '本次消耗日期超出日期用途、确认换算政策或原消费证明的有效期间')
    if basis['standardCapacityId'] != reference['capacityReference']['standardCapacityId']:
        _error('PLAN_DATE_CONSUMPTION_CAPACITY_MISMATCH', '日期用途与原消费关系未绑定同一正式产能')
    return deepcopy(declaration)

class _PolicyReader:
    """Native verified resolves at every persisted effective-period boundary."""
    def __init__(self, user):
        self.user, self.cache, self.proofs = user, {}, {}
        rows = Policy.objects.filter(company_id=user.company_id, status='confirmed')
        self.boundaries = set()
        for start, end in rows.values_list('effective_from', 'effective_to'):
            self.boundaries.add(start)
            if end:
                self.boundaries.add(end + timedelta(days=1))

    def resolve(self, kind, day, *, optional=False, **scope):
        boundary = max((value for value in self.boundaries if value <= day), default=date.min)
        key = kind, tuple(sorted(scope.items())), boundary
        if key not in self.cache:
            try:
                row = policies.resolve_scope(user=self.user, kind=kind, on_date=day, **scope)['row']
            except policies.TimePolicyError as error:
                if optional and error.code == 'POLICY_SCOPE_MISSING':
                    row = None
                else:
                    raise
            self.cache[key] = row
            if row is not None:
                self.proofs[row['id']] = row
        return self.cache[key]

    def revision(self, policy_id):
        if policy_id not in self.proofs:
            self.proofs[policy_id] = policies.read_revision(user=self.user, policy_id=policy_id)['row']
        return self.proofs[policy_id]

    def standard(self, capacity, day):
        basis = self.resolve('CAPACITY_TIME_BASIS', day, standard_capacity_id=capacity.pk)
        shared = self.revision(basis['sharedVersionId'])
        checked = normalize_policy_payload('SHARED_ARRANGEMENT', shared['payload'], strict=True)
        minutes = checked['facts'].get('patterns', {}).get(basis['payload']['standardPattern'], {}).get('processing', {}).get('netMinutes')
        if not checked['ready'] or minutes is None:
            _error('PLAN_DATE_STANDARD_DAY_MISSING', '已确认换算依据未引用完整标准日净加工模式')
        if basis['payload']['standardCapacityHash'] != policies.physical_hash(capacity):
            _error('PLAN_DATE_CAPACITY_CHANGED', '标准产能物理事实已变化，不能沿用原时间换算依据')
        return basis, minutes

    def window(self, capacity, start, end, expected_timezone):
        # Resolve each production-day owner including carry-in. Group equal
        # revisions before invoking the established break/cross-day resolver.
        groups = []
        day = start - timedelta(days=1)
        while day <= end:
            application = self.resolve('WC_APPLICATION', day, work_center_id=capacity.work_center_id)
            shared = self.revision(application['sharedVersionId'])
            selected = self.resolve('SHARED_ARRANGEMENT', day, code=shared['code'])
            if selected['id'] != shared['id']:
                _error('PLAN_DATE_SHARED_REFERENCE_EXPIRED', '中心引用版本与该生产日有效共用制度不一致')
            if shared['payload']['timezone'] != expected_timezone:
                _error('PLAN_DATE_TIMEZONE_MISMATCH', '请求业务时区与正式中心制度时区不一致')
            restrictions = [row for row in (
                self.resolve('OPERATION_RESTRICTION', day, optional=True, operation_id=capacity.operation_id),
                self.resolve('OPERATION_RESTRICTION', day, optional=True, operation_id=capacity.operation_id,
                    work_center_id=capacity.work_center_id)) if row]
            identity = application['id'], shared['id'], tuple(row['id'] for row in restrictions)
            if groups and groups[-1]['identity'] == identity:
                groups[-1]['end'] = day
            else:
                groups.append(dict(identity=identity, start=day, end=day, application=application,
                    shared=shared, restrictions=restrictions))
            day += timedelta(days=1)
        output = dict(companyId=self.user.company_id, workCenterId=capacity.work_center_id,
            timezone=expected_timezone, ready=True, errors=[], resourceIntervals=[], processingIntervals=[],
            configuredProductionDays={}, operationConstraints={}, sourceRevisionIds=[])
        zone = ZoneInfo(expected_timezone)
        lower = datetime.combine(start, time.min, zone)
        upper = datetime.combine(end + timedelta(days=1), time.min, zone)
        for group in groups:
            resolved = resolve_time_window(group['shared']['payload'], center=group['application']['payload'],
                restrictions=[row['payload'] for row in group['restrictions']],
                start_date=(group['start'] - timedelta(days=1)).isoformat(),
                end_date=(group['end'] + timedelta(days=1)).isoformat(),
                company_id=self.user.company_id, work_center_id=capacity.work_center_id)
            if not resolved['ready']:
                output['errors'].extend(resolved['errors'])
                output['ready'] = False
            for field in ('resourceIntervals', 'processingIntervals'):
                for interval in resolved[field]:
                    owner = date.fromisoformat(interval['productionDate'])
                    if group['start'] <= owner <= group['end']:
                        a, b = max(lower, datetime.fromisoformat(interval['start'])), min(upper, datetime.fromisoformat(interval['end']))
                        if a < b:
                            output[field].append({**interval, 'start': a.isoformat(), 'end': b.isoformat()})
            for key, value in resolved['configuredProductionDays'].items():
                if group['start'] <= date.fromisoformat(key) <= group['end']:
                    output['configuredProductionDays'][key] = value
            constraints = resolved.get('operationConstraints', {})
            if constraints.get('interruptible') is False:
                output['operationConstraints']['interruptible'] = False
            minimum = max(Decimal(output['operationConstraints'].get('minimumContinuousMinutes', '0')),
                Decimal(constraints.get('minimumContinuousMinutes', '0')))
            output['operationConstraints']['minimumContinuousMinutes'] = str(minimum)
            output['sourceRevisionIds'].extend([group['application']['id'], group['shared']['id'],
                *[row['id'] for row in group['restrictions']]])
        output['sourceRevisionIds'] = sorted(set(output['sourceRevisionIds']))
        return output

def _display_decimal(value):
    """Format a proved decimal for reading without changing its exact value."""
    rendered = format(Decimal(str(value)), 'f')
    return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered

def _display_datetime(value, timezone_name):
    # Keep the original ISO timestamp, offset and microseconds on start/end.
    # This projection only changes how the same instant is read by the user.
    return datetime.fromisoformat(value).astimezone(ZoneInfo(timezone_name)).strftime('%Y年%m月%d日 %H:%M:%S')

def _labels(row, timezone_name):
    dependent = row.get('dependencyOnly') is True
    applicability = row.get('applicability') or {}
    phase_status = (row['statusLabel'] if dependent and applicability.get('result')
        in {'NOT_APPLICABLE', 'PENDING'} else None)
    saved = row.get('savedLoadReference') or {}
    quantity = saved.get('quantity') if dependent else row['processDemandQuantity']
    uom_label = saved.get('uomLabel') if dependent else row['processDemandUomLabel']
    capacity = row.get('applicableCapacity')
    if capacity is not None:
        period = Decimal(capacity['timeBasisQuantity'])
        capacity_label = (f"{_display_decimal(capacity['quantity'])}{capacity['uomLabel']}／"
            + ('天' if period == 1 else f'{_display_decimal(period)}天'))
    else:
        capacity_label = phase_status or '不适用：无独立定量工期'
    references = row.get('timeReferences') or {}

    def unmeasured_phase(phase, name):
        if phase_status is not None:
            return phase_status
        field = phase + 'Days'
        has_reference = ((references.get('step') or {}).get(field) is not None
            or any(reference.get(field) is not None for reference in references.get('standardCapacities', [])))
        return (f'保留已有{name}参考，不计独立定量工期' if has_reference else f'无独立{name}用时')

    return dict(startLabel=('依赖承接时点：' if dependent else '') + _display_datetime(row['start'], timezone_name),
        endLabel=('无独立工期；承接时点：' if dependent else '') + _display_datetime(row['end'], timezone_name),
        quantityLabel=(f'{_display_decimal(quantity)}{uom_label}' if quantity is not None and uom_label
            else phase_status or saved.get('persistence', {}).get('quantityStatusLabel') or row['statusLabel']),
        capacityLabel=capacity_label,
        standardDayLabel=(f"{_display_decimal(row['standardDayMinutes'])}分钟" if row.get('standardDayMinutes') is not None
            else phase_status or '不适用：无独立定量工期'),
        processingTimeLabel=f"加工{_display_decimal(row['processingMinutes'])}分钟" if row['processingMinutes'] is not None else phase_status or '无独立加工工期',
        preparationTimeLabel=f"准备{_display_decimal(row['preparationMinutes'])}分钟，整步骤一次" if row['preparationMinutes'] is not None else unmeasured_phase('preparation', '准备'),
        transferTimeLabel=f"转运{_display_decimal(row['transferMinutes'])}分钟，整步骤一次" if row['transferMinutes'] is not None else unmeasured_phase('transfer', '转运'),
        totalWorkTimeLabel=f"合计{_display_decimal(row['totalWorkMinutes'])}工作分钟" if row['totalWorkMinutes'] is not None else phase_status or '依赖承接节点，不计独立定量工期')

def _finish(result):
    raw = result.pop('readiness')
    result['stepCount'] = len(raw['steps'])
    result['displayLabels'].update(
        planLabel=result['productionPlanNo'],
        stepCountLabel=f"{result['stepCount']}步",
        timezoneLabel=display_timezone_label(result['timezone']),
        readOnlyLabel='本次结果为只读预览，尚未保存正式排程。')
    result['originalReadiness'] = raw
    result['readiness'] = dict(contractVersion=CONTRACT, factSource='server',
        evaluationScope=dict(type='PLAN_EFFECTIVE_STEPS_FORMAL_WORK_TIME', wholeRouteEvaluated=True,
            **result['scope']), effectiveStepSourcesValidated=raw.get('effectiveStepSourcesValidated', True),
        planningReady=result['previewReady'], blockers=deepcopy(result['blockers']),
        statusLabel=result['statusLabel'], steps=[dict(stepId=row['stepId'], sequence=row['sequence'],
            operationId=row['operationId'], statusLabel=row['statusLabel'],
            engineeringVersion=row.get('engineeringVersion'), predecessorSequences=row['predecessorSequences'])
            for row in result['dates']], businessWriteCount=0, productionScheduleCreatedCount=0)
    result['resultHash'] = _hash(result)
    return result

def _non_quantified_dependency(read):
    """A formal zero policy keeps saved load and topology, never invents zero work."""
    if len(read.get('steps', [])) != 1:
        return False
    row = read['steps'][0]
    semantics = row.get('capacitySemantics') or {}
    source = read.get('allocationRead', {}).get('sourceRead') or {}
    exact = source.get('scope') or {}
    return bool(exact and read['allocationRead'].get('passed') is True
        and row.get('capacityDateMode') == 'AUXILIARY_NO_INDEPENDENT_DATE'
        and row.get('applicability', {}).get('result') == 'REQUIRED'
        and semantics.get('valid') is True and semantics.get('meaningCode') == 'NON_QUANTIFIED'
        and semantics.get('independentDurationAllowed') is False
        and semantics.get('quantitativeOccupancyAllowed') is False
        and all(semantics.get('scope', {}).get(key) == value for key, value in exact.items())
        and source.get('savedAllocations', {}).get('statusCode') == 'SAVED'
        and not read.get('blockers') and not row.get('blockers'))

@transaction.atomic
def formal_plan_date_preview(plan, *, user, start_date, timezone):
    if not timezone:
        _error('PLAN_DATE_TIMEZONE_REQUIRED', '日期预览必须明确业务时区')
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        _error('PLAN_DATE_TIMEZONE_INVALID', '日期预览业务时区无效')
    plan, output, item, company_id = _plan_capacity_context(plan, user.company_id)
    readiness, contexts = DailyCapacityReadinessService.assess_plan_date_scope(
        plan, company_id=company_id, on_date=start_date, user=user)
    # The current capacity reader supplies effective step facts. Freeze each
    # real root/effective engineering identity through its native resolver.
    from .plan_step_context_service import resolve_step_context,version_fact
    for row in readiness['steps']:
        context=resolve_step_context(plan,row.get('rootStepId',row['stepId']),user=user)
        if context['step'].pk!=row['stepId']:
            _error('PLAN_DATE_STEP_IDENTITY_CHANGED','产能步骤与当前工程版本身份不一致')
        row['rootStepId']=context['root_step'].pk
        row['engineeringVersion']=version_fact(context)
    result = dict(contractVersion=CONTRACT, factSource='server', companyId=company_id,
        productionPlanId=plan.pk, productionPlanNo=plan.plan_no,
        scope=dict(companyId=company_id, productionPlanId=plan.pk, rootRoutingVersionId=output.routing_version_id),
        startDateInput=start_date.isoformat(), timezone=timezone, assessedAt=django_timezone.now().isoformat(),
        readiness=readiness, previewReady=False, statusLabel='正式日期预览受阻', dates=[], blockers=[],
        processDemandBlockers=[], processDemandFacts=[], businessWriteCount=0, auditWriteCount=0,
        resourceOccupationCreatedCount=0, productionScheduleCreatedCount=0, mrpRunCount=0,
        formalScheduleSaved=False, actualConflictCheck='REQUEST_LOCAL_PROCESSING_ONLY',
        displayLabels=dict(startLabel='尚未生成', endLabel='尚未生成', scopeLabel='当前计划全路线',
            timeBasisLabel='按已确认标准日换算，并在各中心正式有效工作时段累计',
            resourceRuleLabel='加工沿正式工作中心资源规则；准备与转运仅累计工作时间；无持久化占用'))
    if plan.status != 'confirmed' or output.release_status != 'released_to_manufacturing' or output.routing_version.status != 'released':
        result['blockers'].append(dict(code='PLAN_SOURCE_NOT_RELEASED', statusLabel='生产计划、制造输出或路线尚未正式确认发布'))
        return _finish(result)
    reader, cache, native_rows = _PolicyReader(user), _source_read_cache(user, None), {}
    # One native proof per step; original blockers remain under originalReadiness.
    for row in readiness['steps']:
        try:
            read = AllocatedLoadCapacityReadinessService._assess_read(user=user,
                production_plan_id=plan.pk, routing_step_id=row['rootStepId'] if 'rootStepId' in row else row['stepId'],
                on_date=start_date, read_cache=cache)
            if len(read['steps']) != 1:
                blockers = read.get('blockers') or [dict(code='PLAN_DATE_STEP_SOURCE_MISSING', statusLabel='未取得本步骤单一正式负荷事实')]
            else:
                native_rows[row['sequence']] = read
                native = read['steps'][0]
                blockers = read.get('blockers', []) + native.get('blockers', [])
                if not (read.get('scopeNoDateReady') is True or read.get('legalEmptyLoadVerified') is True
                        or _non_quantified_dependency(read)):
                    blockers = blockers or [dict(code='PLAN_DATE_STEP_LOAD_UNPROVEN', statusLabel=read['statusLabel'])]
            seen = set()
            for blocker in blockers:
                key = blocker['code'], blocker.get('statusLabel', blocker.get('label', ''))
                if key in seen:
                    continue
                seen.add(key)
                result['blockers'].append(dict(stepId=row['stepId'], sequence=row['sequence'], operationId=row['operationId'],
                    code=key[0], statusLabel=key[1]))
            result['processDemandFacts'].extend(read.get('processDemandFacts', []))
        except Exception as error:
            if not hasattr(error, 'code'):
                raise
            result['blockers'].append(dict(stepId=row['stepId'], sequence=row['sequence'], operationId=row['operationId'],
                code=error.code, statusLabel=getattr(error, 'message', str(error))))
    if result['blockers']:
        result['processDemandBlockers'] = deepcopy(result['blockers'])
        return _finish(result)
    pending = {row['sequence']: row for row in readiness['steps']}
    finished, bookings = {}, {}
    while pending:
        eligible = [row for row in pending.values() if all(p in finished for p in row['predecessorSequences'])]
        if not eligible:
            _error('ROUTING_DEPENDENCY_CYCLE', '有效步骤路线存在循环或缺失依赖')
        row = min(eligible, key=lambda value: value['sequence'])
        earliest = max([datetime.combine(start_date, time.min, zone)] +
            [datetime.fromisoformat(finished[p]['end']) for p in row['predecessorSequences']])
        native_read = native_rows[row['sequence']]
        native = native_read['steps'][0]
        common = dict(stepId=row['stepId'], rootStepId=row.get('rootStepId', row['stepId']), sequence=row['sequence'],
            operationId=row['operationId'], operationName=row.get('operationName', native.get('operationName', '')),
            predecessorSequences=row['predecessorSequences'], engineeringVersion=row.get('engineeringVersion'),
            applicability=deepcopy(native['applicability']))
        try:
            if native_read.get('legalEmptyLoadVerified') or _non_quantified_dependency(native_read):
                projected = dict(common, start=earliest.isoformat(), end=earliest.isoformat(),
                    workCenterId=None, standardCapacityId=None, processingMinutes=None,
                    preparationMinutes=None, transferMinutes=None, totalWorkMinutes=None, phases=[],
                    statusLabel=(native['statusLabel'] + '；仅显示依赖承接时点，无独立加工工期')
                        if _non_quantified_dependency(native_read) else native['statusLabel'],
                    timeReferences=native.get('timeReferences'), capacitySemantics=native.get('capacitySemantics'),
                    savedLoadReference=native_read.get('allocationRead', {}).get('sourceRead', {}).get('savedAllocations'),
                    dependencyOnly=True, quantitativeOccupancyAllowed=False)
            else:
                matches = native['capacityMatches']
                if len(matches) != 1:
                    _error('PLAN_DATE_CAPACITY_AMBIGUOUS', '本步骤没有唯一经保存负荷证明的适用产能')
                match = matches[0]
                reference = native_read.get('capacityConsumptionReference')
                fact = match['capacityFact']
                capacity = _current_plan_capacity(fact, start_date, no_date_reference=reference)
                if capacity.resource_scope != 'work_center':
                    _error('PLAN_DATE_RESOURCE_RULE_UNSUPPORTED', '本只读预览尚未实现该正式资源范围规则')
                basis, standard_minutes = reader.standard(capacity, earliest.date())
                exact_scope = native_read['allocationRead']['sourceRead']['scope']
                if reference is not None:
                    validate_date_consumption(basis, reference, exact_scope=exact_scope, on_date=earliest.date())
                demand = native['processDemand']
                # required_duration_days on saved allocations is historical
                # trace only: this consumer reuses the formal selected load and
                # explicit phase basis once; it never adds frozen totals again.
                for phase, day_field in (('preparation', 'preparationDays'), ('transfer', 'transferDays')):
                    source_days = Decimal(match[day_field])
                    selected = basis['payload'][phase]
                    converted = normalize_policy_payload('CAPACITY_TIME_BASIS', basis['payload'], strict=True)
                    if (not converted['ready'] or Decimal(converted['facts'][phase]['minutes']) != source_days * Decimal(standard_minutes)):
                        _error('PLAN_DATE_PHASE_SOURCE_CONFLICT', '确认时间换算值与本次正式选择的准备或转运DAY来源不一致')
                window = reader.window(capacity, earliest.date(), earliest.date() + timedelta(days=60), timezone)
                calculated = preview_operation_time(window, demand_quantity=demand['quantity'],
                    capacity_quantity=str(capacity.quantity), basis=basis['payload'], standard_day_minutes=standard_minutes,
                    not_before=earliest, company_id=company_id, work_center_id=capacity.work_center_id, bookings=bookings)
                if not calculated['ready']:
                    result['blockers'].extend(dict(stepId=row['stepId'], sequence=row['sequence'], operationId=row['operationId'],
                        code=issue['code'], statusLabel=issue.get('message', str(issue))) for issue in calculated['errors'])
                    result['diagnosticPartialSteps'] = list(finished.values())
                    return _finish(result)
                consumed = sorted({date.fromisoformat(part['productionDate']) for phase in calculated['phases']
                    for part in phase['allocations']})
                for day in consumed:
                    current_basis, current_minutes = reader.standard(capacity, day)
                    if current_basis['id'] != basis['id'] or current_minutes != standard_minutes:
                        _error('PLAN_DATE_BASIS_WINDOW_SPLIT_REQUIRED', '步骤消耗跨时间换算政策边界，必须显式分段计算')
                    if reference is not None:
                        validate_date_consumption(current_basis, reference, exact_scope=exact_scope, on_date=day)
                    if any((getattr(model, 'effective_from', None) and day < model.effective_from)
                            or (getattr(model, 'effective_to', None) and day > model.effective_to)
                            for model in (capacity, capacity.work_center, capacity.operation, capacity.product_type)):
                        _error('CAPACITY_EFFECTIVE_WINDOW_MISMATCH', '实际消耗日期超出正式产能或资源有效期间')
                validate_capability_window(row, capacity, [{'date': day.isoformat()} for day in consumed])
                bookings = calculated['bookings']
                phase_minutes = {phase['phase']: phase['minutes'] for phase in calculated['phases']}
                projected = dict(common, start=calculated['start'], end=calculated['end'], workCenterId=capacity.work_center_id,
                    standardCapacityId=capacity.pk, processDemandQuantity=demand['quantity'], processDemandUomId=demand['uomId'],
                    processDemandUomLabel=fact['uomLabel'], applicableCapacity={key: deepcopy(fact[key])
                        for key in ('id', 'code', 'quantity', 'uomId', 'uomLabel', 'timeBasis', 'timeBasisQuantity')},
                    processingMinutes=calculated['processingMinutes'], preparationMinutes=phase_minutes['preparation'],
                    transferMinutes=phase_minutes['transfer'], totalWorkMinutes=str(sum((Decimal(value) for value in phase_minutes.values()), Decimal(0))),
                    standardDayMinutes=standard_minutes, productionStandardDays=calculated['productionStandardDays'],
                    phases=calculated['phases'], statusLabel='正式来源与有效工作时段日期预览已计算',
                    timeSelection=match.get('timeSelection', row.get('timeSelection')), sourceRevisionIds=sorted(set(
                        window['sourceRevisionIds'] + [basis['id'], basis['sharedVersionId']])),
                    capacityConsumptionReference=reference, requiredDurationTreatment='FORMAL_LOAD_AND_PHASES_ONCE_NO_FROZEN_TOTAL_ADDITION',
                    resourceRule=dict(processing='StandardCapacity.resource_scope=work_center',
                        preparation=basis['payload']['preparation']['occupancy'], transfer=basis['payload']['transfer']['occupancy']))
        except Exception as error:
            if not hasattr(error, 'code'):
                raise
            result['blockers'].append(dict(stepId=row['stepId'], sequence=row['sequence'], operationId=row['operationId'],
                code=error.code, statusLabel=getattr(error, 'message', str(error))))
            result['diagnosticPartialSteps'] = list(finished.values())
            return _finish(result)
        projected.update(startDate=projected['start'][:10], endDate=projected['end'][:10])
        projected['displayLabels'] = _labels(projected, timezone)
        finished[row['sequence']] = projected
        pending.pop(row['sequence'])
    # Re-read all revision/audit proofs before publishing a single final result.
    for policy_id, proof in reader.proofs.items():
        if policies.read_revision(user=user, policy_id=policy_id)['row'] != proof:
            _error('PLAN_DATE_POLICY_CHANGED', '时间配置在本次只读计算期间发生变化，请重新预览')
    result['timePolicyProofs'] = [{key: deepcopy(proof[key]) for key in
        ('id', 'kind', 'kindLabel', 'code', 'revision', 'contentHash', 'effectiveFrom', 'effectiveTo',
         'sharedVersionId', 'workCenterId', 'operationId', 'standardCapacityId', 'confirmationBasis',
         'confirmedAt', 'stateTransitionHistory', 'statusTransitionCount')}
        for _, proof in sorted(reader.proofs.items())]
    result.update(previewReady=True, statusLabel='当前计划全路线正式只读日期预览已计算',
        dates=sorted(finished.values(), key=lambda value: value['sequence']),
        start=min(value['start'] for value in finished.values()), end=max(value['end'] for value in finished.values()))
    result['startDate'], result['endDate'] = result['start'][:10], result['end'][:10]
    result['displayLabels'].update(startLabel=_display_datetime(result['start'], timezone),
        endLabel=_display_datetime(result['end'], timezone))
    return _finish(result)
