"""Zero-write engineering summaries; preview quantities never become formal facts.

Existing source projections are accepted only as preview snapshots. Saved
conversion proofs come exclusively from fixed calculation/Fact/EOR foreign keys.
This module neither evaluates a rule nor creates a business record.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .engineering_rule_foundation import canonical_json
from .models import (
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringRuleDefinition,
    EngineeringSourceRecord, ProductDesignItem, ProductManufacturingOutput,
)
from .operation_requirement_service import (
    OperationRequirementError, OperationRequirementService, VIEW, _active, _authorize,
    _source_read_cache,
)

CONTRACT = 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1'
FACT_SURFACES = ('apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts')
NATURE_LABELS = {
    'CURRENT_PRODUCT_DESIGN_CALCULATION_PREVIEW': '当前产品设计工程量预览',
    'CURRENT_INPUT_COMPARISON_PREVIEW': '当前输入工程量预览',
    'HISTORICAL_APPROVED_SOURCE_PREVIEW': '历史来源工程量预览',
    'FORMAL_SAVED_DERIVED_FACT': '已保存正式工程派生事实',
}


def _reason(code, label):
    return {'code': code, 'statusLabel': label}


def _data_type(project, *, formal_dimension=None):
    # The existing engineering project declaration describes the data itself
    # (area, net length, casing quantity, etc.). A unit never selects a Process
    # or makes a result eligible for operation-demand generation.
    declared_types = {'area': ('AREA', '面积'), 'length': ('LENGTH', '长度'),
        'count': ('QUANTITY', '数量')}
    if formal_dimension in declared_types:
        code, label = declared_types[formal_dimension]
        return {'dataTypeCode': code, 'dataTypeLabel': label, 'dataTypeAuthority': 'FORMAL_UOM_DIMENSION'}
    if isinstance(project, str) and project.strip():
        return {'dataTypeCode': 'SOURCE_PROJECT_DECLARATION', 'dataTypeLabel': project}
    return {'dataTypeCode': 'UNKNOWN', 'dataTypeLabel': '未知工程数据类型'}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _records(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _decimal(value):
    if value is None or value == '' or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def _text(value):
    if value is None:
        return None
    rendered = format(value, 'f')
    return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered


def _sum(values):
    known = [value for value in values if value is not None]
    if not known:
        return None
    # Summaries retain supplied decimal facts exactly; no float conversion or
    # new output-scale/rounding policy is introduced by this presentation.
    with localcontext() as context:
        context.prec = max(40, sum(len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                                  for value in known) + 8)
        return sum(known, Decimal(0))


def _unique_reasons(reasons):
    seen, result = set(), []
    for reason in reasons:
        key = (reason.get('code'), reason.get('statusLabel'))
        if key not in seen:
            seen.add(key)
            result.append(reason)
    return result


def _native_rule_count(company_id):
    return sum(1 for rule in EngineeringRuleDefinition.objects.filter(company_id=company_id,
        status='released') if _active(rule) and any(output.get('resultDomain') == 'OPERATION_REQUIREMENT'
        for output in _records(_mapping(rule.specification).get('outputs'))))


def _source_index(rows):
    result = {}
    for source in _records(rows):
        key = source.get('sourceKey') or f"{source.get('sourceSheet') or ''}:{source.get('sourceRow')}"
        result.setdefault(str(key), []).append(source)
    return result


def _source_type(source, sheet):
    # These labels describe contribution provenance only. They never select a
    # Process, capacity, quantity basis or formal conversion rule.
    declared = source.get('sourceType')
    if declared in {'房门单', '三合一单'}:
        return declared
    return {'房门单': '房门单', '三合一生产单': '三合一单'}.get(sheet, '其他来源')


def _contributions(items):
    return {**{name: _text(_sum([_decimal(item.get('quantity')) for item in items
        if item.get('sourceType') == label])) for name, label in (
            ('door', '房门单'), ('threeInOne', '三合一单'), ('other', '其他来源'))},
        'items': items}


def _preview_rows(draft, snapshot, snapshot_key, workshop):
    rows = _records(snapshot.get('rows'))
    nature = snapshot.get('resultNature') or (
        'HISTORICAL_APPROVED_SOURCE_PREVIEW' if snapshot_key == 'sourceCalculation'
        else 'CURRENT_INPUT_COMPARISON_PREVIEW')
    nature_label = NATURE_LABELS.get(nature, '工程量预览（来源性质未完整声明）')
    source_rows = draft.get('workOrderRows') if snapshot_key == 'currentInputCalculation' else draft.get('rows')
    source_index = _source_index(source_rows)
    if not source_index:
        source_index = _source_index(draft.get('rows'))
    # Reuse the existing preview's explicit additive result-ID contract.
    # Other engineering results, including dimensions, remain individual rows.
    additive_ids = {str(result_id) for total in _records(snapshot.get('totals'))
        if total.get('net') is not None for result_id in (total.get('ids') or [])}
    groups = {}
    for ordinal, result in enumerate(rows):
        result_id = str(result.get('id') or f'{snapshot_key}:{ordinal}')
        source_key = str(result.get('sourceKey') or f"{result.get('sheet') or ''}:{result.get('row')}")
        matches = source_index.get(source_key, [])
        source = matches[0] if len(matches) == 1 else {}
        code_field = 'materialProcessCode' if workshop == 'paint' else 'routingProcessCode'
        code = str(source.get(code_field) or '')
        unit = result.get('unit') or None
        project = str(result.get('project') or result.get('column') or '')
        additive = result_id in additive_ids
        identity = [snapshot_key, nature, result.get('resultScope'), code, project, unit,
                    result.get('ruleVersion'), None if additive else ordinal]
        key = sha256(canonical_json(identity).encode('utf-8')).hexdigest()
        group = groups.setdefault(key, {'key': key, 'sourceCode': code, 'sourceProject': project,
            **_data_type(result.get('project')),
            'UOM': {'id': None, 'code': unit, 'label': unit, 'authority': 'PREVIEW_UNIT_SNAPSHOT'},
            'uomCode': unit, 'uomLabel': unit, 'sourceNatureCode': nature,
            'sourceNatureLabel': nature_label, 'aggregationBasis': 'EXISTING_PREVIEW_ADDITIVE_CONTRACT'
                if additive else 'INDIVIDUAL_SOURCE_RESULT', 'items': [], 'missingReasons': [],
            'operationRequirementIds': [], 'statusCode': 'PREVIEW_UNBOUND',
            'statusLabel': '工程量预览；未证明与固定正式来源事实相同',
            'conversion': {'conversionStatusCode': 'PREVIEW_UNBOUND',
                'statusLabel': '预览不具有正式工序需求转换资格', 'operationRequirementIds': []}})
        quantity = _decimal(result.get('value'))
        reasons = [_reason('PREVIEW_FIXED_SOURCE_UNPROVEN',
            '预览没有正式Calc/Fact外键，不能据此判断已转换或替代正式工序需求')]
        if not code:
            reasons.append(_reason('SOURCE_GROUP_CODE_MISSING', '来源分组编码缺失；原工程量及贡献继续显示'))
        if len(matches) != 1:
            reasons.append(_reason('SOURCE_CONTRIBUTION_MAPPING_UNPROVEN',
                '来源贡献没有唯一预览行关联，未根据名称或单位补齐编码'))
        if not unit:
            reasons.append(_reason('SOURCE_UOM_MISSING', '来源未声明单位；保留数量且不与其他单位合并'))
        if quantity is None:
            reasons.append(_reason('SOURCE_QUANTITY_MISSING' if result.get('value') in (None, '')
                else 'SOURCE_QUANTITY_INVALID', result.get('reason') or '来源工程数量未知，未以0补齐'))
        item = {'id': result_id, 'sourceKey': source_key, 'sheet': result.get('sheet'),
            'row': result.get('row'), 'sourceColumn': result.get('column'), 'sourceProject': project,
            'quantity': _text(quantity), 'sourceValue': deepcopy(result.get('value')), 'uomCode': unit,
            'sourceType': _source_type(source, result.get('sheet')),
            'sourceNatureCode': nature, 'sourceNatureLabel': nature_label,
            'sourceResultScope': result.get('resultScope'), 'sourceStatusLabel': result.get('statusLabel'),
            'ruleVersion': result.get('ruleVersion'), 'sourceCode': code,
            'missingReasons': reasons}
        group['items'].append(item)
        group['missingReasons'].extend(reasons)
    projected = []
    for group in groups.values():
        items = group.pop('items')
        group.update(quantity=_text(_sum([_decimal(item['quantity']) for item in items])),
            knownCount=sum(item['quantity'] is not None for item in items),
            missingCount=sum(item['quantity'] is None for item in items),
            contributions=_contributions(items), missingReasons=_unique_reasons(group['missingReasons']))
        projected.append(group)
    return projected


def _fixed_calculations(user, draft, explicit_ids):
    if explicit_ids is not None:
        if (not isinstance(explicit_ids, list) or any(type(value) is not int or value <= 0 for value in explicit_ids)
            or len(set(explicit_ids)) != len(explicit_ids)):
            raise OperationRequirementError('SOURCE_CALCULATION_MISSING', '核算ID必须是明确且不重复的正式整数ID')
        rows = list(EngineeringCalculationRecord.objects.filter(pk__in=explicit_ids,
            company_id=user.company_id).order_by('pk'))
        if len(rows) != len(explicit_ids):
            raise OperationRequirementError('SOURCE_CALCULATION_MISSING', '核算不属于当前公司的正式工程来源范围')
        if any(row.scope != 'order_engineering' for row in rows):
            raise OperationRequirementError('SOURCE_SCOPE_UNSUPPORTED',
                '该核算范围不支持正式工程作业量承接；原核算数据继续保留')
        return rows, [{'sourceCalculationId': row.pk, 'authority': 'EXPLICIT_CALCULATION_FK'} for row in rows]
    source_id = draft.get('id')
    if type(source_id) is not int or not EngineeringSourceRecord.objects.filter(
        pk=source_id, company_id=user.company_id).exists():
        return [], []
    item_ids = ProductDesignItem.objects.filter(company_id=user.company_id,
        source_record_id=source_id).values_list('sales_order_item_id', flat=True)
    outputs = ProductManufacturingOutput.objects.filter(
        order_engineering_instance__company_id=user.company_id,
        order_engineering_instance__sales_order_item_id__in=item_ids,
        engineering_calculation__company_id=user.company_id,
        engineering_calculation__source_record_id=source_id,
        release_status='released_to_manufacturing').select_related(
            'engineering_calculation', 'order_engineering_instance').order_by('pk')
    pins, calculations = [], {}
    for output in outputs:
        calculation = output.engineering_calculation
        if (calculation.scope != 'order_engineering'
            or calculation.engineering_instance_id != output.order_engineering_instance_id
            or calculation.sales_order_item_id != output.order_engineering_instance.sales_order_item_id):
            continue
        calculations[calculation.pk] = calculation
        pins.append({'manufacturingOutputId': output.pk, 'sourceCalculationId': calculation.pk,
            'sourceRecordId': source_id, 'salesOrderItemId': calculation.sales_order_item_id,
            'authority': 'MANUFACTURING_OUTPUT_FIXED_CALCULATION_FK'})
    return list(calculations.values()), pins


def _formal_rows(user, calculations, *, read_cache=None):
    rows, source_reasons, verified_ids = [], [], set()
    for calculation in calculations:
        try:
            conversion = OperationRequirementService.read_source_conversion(
                user=user, source_calculation_id=calculation.pk, _read_cache=read_cache)
            conversion_by_fact = {fact['sourceFactId']: fact for fact in conversion['facts']}
            if conversion['unmappedOperationRequirementIds']:
                source_reasons.append(_reason('LEGACY_OPERATION_SOURCE_UNPROVEN',
                    '既有工序需求缺少精确来源Fact外键，未归入转换结论'))
        except OperationRequirementError as exc:
            conversion_by_fact = {}
            source_reasons.append(_reason(exc.code, exc.message))
        trace = _mapping(calculation.trace)
        results = _records(trace.get('resultSnapshot'))
        for fact in EngineeringDerivedFact.objects.filter(calculation=calculation).select_related(
            'source_detail', 'uom').order_by('sequence', 'pk'):
            result_matches = [result for result in results if result.get('factId') == fact.pk
                and result.get('detailId') == fact.source_detail_id
                and result.get('canonicalField') == fact.canonical_field and result.get('value') == fact.value]
            result = result_matches[0] if len(result_matches) == 1 else {}
            detail = fact.source_detail
            object_input = _mapping(_mapping(detail.input_snapshot).get('object')) if detail else {}
            source_key = result.get('sourceKey') or _mapping(fact.trace).get('sourceKey')
            frozen_source = object_input.get('input') if isinstance(object_input.get('input'), dict) else object_input
            source_unit = fact.uom.code if fact.uom_id else None
            quantity = _decimal(_mapping(fact.value).get('decimal'))
            source_project = result.get('displayName') or (detail.output_name if detail else None) or fact.canonical_field
            status = conversion_by_fact.get(fact.pk) or {
                'conversionStatusCode': 'BLOCKED', 'statusLabel': '正式转换来源校验未完成',
                'operationRequirementIds': [], 'requirements': [], 'ruleCandidates': [],
                'blockers': source_reasons[-1:] or [_reason('SOURCE_CONVERSION_READ_FAILED', '正式转换事实未能读取')]}
            reasons = list(status['blockers'])
            if not result:
                reasons.append(_reason('SOURCE_RESULT_MAPPING_UNPROVEN',
                    '固定核算未保存唯一Fact/Detail结果映射；未关联到预览贡献'))
            if quantity is None:
                reasons.append(_reason('SOURCE_QUANTITY_MISSING', '已保存工程数量未知，未以0替代'))
            if not source_unit:
                reasons.append(_reason('SOURCE_UOM_MISSING', '已保存工程事实未绑定正式单位，未推测单位'))
            item = {'id': f'fact:{fact.pk}', 'sourceCalculationId': calculation.pk,
                'sourceFactId': fact.pk, 'sourceDetailId': fact.source_detail_id,
                'sourceKey': source_key, 'sourceProject': source_project,
                'sheet': frozen_source.get('sourceSheet'), 'row': frozen_source.get('sourceRow'),
                'sourceColumn': fact.canonical_field, 'quantity': _text(quantity), 'uomCode': source_unit,
                'sourceType': _source_type({}, frozen_source.get('sourceSheet')),
                'sourceNatureLabel': NATURE_LABELS['FORMAL_SAVED_DERIVED_FACT'],
                'designItemId': result.get('designItemId'), 'designItemNo': result.get('designItemNo')}
            verified_ids.update(status['operationRequirementIds'])
            rows.append({'key': f'formal:{calculation.pk}:{fact.pk}',
                'sourceCalculationId': calculation.pk, 'sourceCalculationNo': calculation.calculation_no,
                'sourceFactId': fact.pk, 'sourceDetailId': fact.source_detail_id,
                'sourceRecordId': calculation.source_record_id, 'salesOrderItemId': calculation.sales_order_item_id,
                'sourceCode': frozen_source.get('routingProcessCode') or '', 'sourceProject': source_project,
                'sourceCanonicalField': fact.canonical_field,
                **_data_type(result.get('displayName') or (detail.output_name if detail else None),
                    formal_dimension=fact.uom.dimension if fact.uom_id else None),
                'quantity': _text(quantity),
                'UOM': {'id': fact.uom_id, 'code': source_unit,
                    'label': fact.uom.name if fact.uom_id else None, 'authority': 'FORMAL_UOM_FK'},
                'uomCode': source_unit, 'uomLabel': fact.uom.name if fact.uom_id else None,
                'sourceNatureCode': 'FORMAL_SAVED_DERIVED_FACT',
                'sourceNatureLabel': NATURE_LABELS['FORMAL_SAVED_DERIVED_FACT'],
                'knownCount': int(quantity is not None), 'missingCount': int(quantity is None),
                'contributions': _contributions([item]), 'statusCode': status['conversionStatusCode'],
                'statusLabel': status['statusLabel'], 'missingReasons': _unique_reasons(reasons),
                'operationRequirementIds': status['operationRequirementIds'], 'conversion': status})
    return rows, source_reasons, verified_ids


@transaction.atomic
def build_engineering_workload_summary(*, user, draft=None, source_calculation_ids=None):
    """Appendable server projection over existing previews and fixed saved facts."""
    _authorize(user, VIEW)
    # This read owns one snapshot and proof-read cache; neither survives it.
    read_cache = _source_read_cache(user, None)
    draft = _mapping(draft)
    if type(draft.get('id')) is int and not EngineeringSourceRecord.objects.filter(
        pk=draft['id'], company_id=user.company_id).exists():
        raise OperationRequirementError('SOURCE_FACT_MISMATCH', '工程预览来源不属于当前公司或已无法读取')
    workshop_views = {key: {'label': label, 'rows': []} for key, label in (
        ('paint', '来源材料编码视图'), ('wood', '来源工艺编码视图'))}
    source_snapshots, reasons = [], []
    for snapshot_key in ('currentInputCalculation', 'sourceCalculation'):
        snapshot = _mapping(draft.get(snapshot_key))
        if not snapshot:
            continue
        source_failed = bool(snapshot.get('detail'))
        source_snapshots.append({'key': snapshot_key, 'sourceNatureCode': snapshot.get('resultNature'),
            'readStatus': 'unknown' if source_failed else 'loaded',
            'readStatusLabel': snapshot.get('readStatusLabel') or '已读取来源工程量预览',
            'detail': snapshot.get('detail'),
            'resultCount': None if source_failed else len(_records(snapshot.get('rows'))),
            'availableResultCount': len(_records(snapshot.get('rows'))),
            'sourceNatureLabel': NATURE_LABELS.get(snapshot.get('resultNature'), '工程量预览'),
            'fingerprint': snapshot.get('fingerprint'), 'inputRevisionHash': snapshot.get('inputRevisionHash')})
        if source_failed:
            reasons.append(_reason('SOURCE_PREVIEW_READ_FAILED',
                f"{snapshot.get('readStatusLabel') or '来源工程量预览读取失败'}：{snapshot.get('detail')}"))
        for workshop in workshop_views:
            workshop_views[workshop]['rows'].extend(_preview_rows(draft, snapshot, snapshot_key, workshop))
    calculations, pins = _fixed_calculations(user, draft, source_calculation_ids)
    formal_rows, formal_reasons, verified_ids = _formal_rows(user, calculations, read_cache=read_cache)
    reasons.extend(formal_reasons)
    rule_count = _native_rule_count(user.company_id)
    if source_snapshots:
        reasons.append(_reason('PREVIEW_FIXED_SOURCE_UNPROVEN',
            '当前及历史预览各自保留；固定正式事实并列展示，未证明预览与其为同一版本输入'))
    if not calculations:
        reasons.append(_reason('FIXED_SOURCE_CALCULATION_MISSING',
            '尚未取得明确核算ID或正式制造输出固定核算FK，不能推测正式转换来源'))
    if not rule_count:
        reasons.append(_reason('OPERATION_RULE_MAPPING_MISSING',
            '当前尚无有效已发布的原生工序需求规则；工程数量与来源贡献继续显示'))
    surface = {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'loaded',
        'readStatusLabel': '已读取工程量、来源贡献及固定正式转换事实',
        'statusCode': 'READ_ONLY_SUMMARY', 'statusLabel': '只读工程量汇总；正式转换结论按来源外键校验',
        'sourceRecordId': draft.get('id'), 'sourceSnapshots': source_snapshots,
        'workshopViews': workshop_views, 'formalSavedFacts': formal_rows, 'fixedSourcePins': pins,
        'missingReasons': _unique_reasons(reasons), 'businessWriteCount': 0,
        'counts': {'previewResultCount': None if any(snapshot['readStatus'] == 'unknown'
                for snapshot in source_snapshots) else sum(snapshot['resultCount'] for snapshot in source_snapshots),
            'availablePreviewResultCount': sum(snapshot['availableResultCount'] for snapshot in source_snapshots),
            'formalFactCount': len(formal_rows), 'verifiedOperationRequirementCount': len(verified_ids),
            'nativeOperationRuleCount': rule_count}}
    # Preserve every existing preview/formal row and its original count contract.
    # The additional business quantities have their own purpose/unit partitions.
    from .engineering_workload_review import build_purpose_review, CONTRACT as REVIEW_CONTRACT
    try:
        surface['purposeReview'] = build_purpose_review(user=user, calculations=calculations,
            _read_cache=read_cache)
    except Exception as exc:
        surface['purposeReview'] = {'contractVersion': REVIEW_CONTRACT, 'factSource': 'server',
            'readStatus': 'read_failed', 'statusLabel': getattr(exc, 'message', '按用途只读评审读取失败'),
            'groups': [], 'operationLoads': [], 'historyRequirements': [],
            'missingReasons': [_reason(getattr(exc, 'code', 'PURPOSE_REVIEW_READ_FAILED'),
                getattr(exc, 'message', '按用途只读评审读取失败；数量未知，未以零替代'))],
            'counts': {'effectiveRequirementCount': None, 'historicalRequirementCount': None},
            'businessWriteCount': 0}
    return stamp_engineering_workload_summary(surface, tenant_id=user.company_id,
        api_url=None, http_status=None)


def engineering_workload_summary_read_failure(error, *, source_record_id=None,
    tenant_id=None, api_url=None, http_status=None, batch_id=None, loaded_at=None):
    """Report an unavailable added projection without replacing original GET data."""
    label = getattr(error, 'message', str(error)) or '工程量汇总暂时无法读取'
    surface = {'contractVersion': CONTRACT, 'factSource': 'server', 'readStatus': 'read_failed',
        'readStatusLabel': label, 'statusCode': 'READ_FAILED', 'statusLabel': label,
        'sourceRecordId': source_record_id, 'sourceSnapshots': [], 'formalSavedFacts': [],
        'fixedSourcePins': [], 'workshopViews': {key: {'label': title, 'rows': []}
            for key, title in (('paint', '来源材料编码视图'), ('wood', '来源工艺编码视图'))},
        'missingReasons': [_reason(getattr(error, 'code', 'ENGINEERING_SUMMARY_READ_FAILED'), label)],
        'errorCode': getattr(error, 'code', 'ENGINEERING_SUMMARY_READ_FAILED'), 'errorMessage': label,
        'businessWriteCount': 0, 'counts': {'previewResultCount': None,
            'availablePreviewResultCount': None, 'formalFactCount': None,
            'verifiedOperationRequirementCount': None, 'nativeOperationRuleCount': None}}
    return stamp_engineering_workload_summary(surface, tenant_id=tenant_id,
        api_url=api_url, http_status=http_status, batch_id=batch_id, loaded_at=loaded_at)


def stamp_engineering_workload_summary(summary, *, tenant_id, api_url, http_status,
    batch_id=None, loaded_at=None):
    """Stamp actual transport context once and rebuild all consumers from it.

    A semantic read failure inside a successful original GET keeps that GET's
    actual HTTP status. Domain-only readers explicitly have no HTTP context.
    """
    surface = {key: deepcopy(value) for key, value in summary.items() if key not in FACT_SURFACES}
    surface.update(factLoadStatus=surface.get('readStatus', 'unknown'), apiUrl=api_url,
        httpStatus=http_status, tenantId=tenant_id,
        batchId=batch_id or surface.get('batchId') or f'engineering-summary-{uuid4().hex}',
        loadedAt=loaded_at or surface.get('loadedAt') or timezone.now().isoformat(),
        errorCode=surface.get('errorCode') or '', errorMessage=surface.get('errorMessage') or '')
    return {**surface, **{key: deepcopy(surface) for key in FACT_SURFACES}}
