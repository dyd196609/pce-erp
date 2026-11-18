from pde.baseline_usage_service import production_status
"""Prove configured metadata against saved, confirmed engineering input.

This resolver reads an existing successful object's frozen input. It does not
infer business classifications, inspect display names, execute calculations,
or load a model named by arbitrary configuration.
"""
from copy import deepcopy

from django.db.models import ForeignKey

from .engineering_rule_foundation import canonical_json
from .models import ManufacturingProcessType, OrderEngineeringBaseline, ProductDesignRevision
from .operation_requirement_service import _digest, _fail


CONTRACT = 'PCE-ENGINEERING-FACT-METADATA-V1'
OBJECT_INPUT_AUTHORITY = 'CONFIRMED_ORDER_ENGINEERING_BASELINE_ITEM'
REGISTERED_REFERENCES = {
    'pde.ManufacturingProcessType': {
        'model': ManufacturingProcessType, 'companyField': 'company_id',
        'activeField': 'is_active', 'valueFields': frozenset(('id', 'code')),
        'inputReferences': {
            ('paintProcessTypeId',): {'sourceModel': ProductDesignRevision,
                'sourceField': 'paint_process_type', 'snapshotPath': ('revision', 'paintProcessTypeId')},
            ('materialProcessTypeId',): {'sourceModel': ProductDesignRevision,
                'sourceField': 'material_process_type', 'snapshotPath': ('revision', 'materialProcessTypeId')},
        },
    },
}
REGISTERED_FROZEN_VALUES = {
    ('routingProcessCode',): {
        'snapshotPaths': (
            ('designItem', 'existingDesignData', 'routingProcessCode'),
            ('source', 'rawValue', 'routingProcessCode'),
        ),
        'evidencePath': ('source', 'rawValue', 'sourceEvidence', 'C'),
        'evidenceColumn': 'C',
    },
}
REGISTERED_SOURCE_IDENTITIES = frozenset((
    'sourceFactId', 'sourceCalculationId', 'sourceDetailId', 'baselineId',
    'baselineItemId', 'designItemId', 'sourceAttributeId', 'sourceRecordId',
))
RESERVED_TRACE_KEYS = frozenset((
    'contractVersion', 'resultDomain', 'detailId', 'ruleCode', 'ruleVersion',
    'specificationHash', 'outputKey', 'outputHash', 'baseEngineeringCalculationId',
    'group', 'calculatedAt', 'metadata', 'inputHash',
))


def _name(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _registered_input_reference(path):
    if not isinstance(path, list) or not path or any(not _name(part) for part in path):
        _fail('FACT_METADATA_CONFIG_INVALID', '冻结对象条件必须声明精确且已注册的正式字段路径')
    references = [row['inputReferences'][tuple(path)] for row in REGISTERED_REFERENCES.values()
                  if tuple(path) in row['inputReferences']]
    if len(references) != 1:
        _fail('FACT_METADATA_CONFIG_INVALID', '冻结对象条件只能使用已注册的正式对象引用字段')
    reference = references[0]
    if not isinstance(reference['sourceModel']._meta.get_field(reference['sourceField']), ForeignKey):
        _fail('FACT_METADATA_CONFIG_INVALID', '冻结对象条件必须对应当前正式Schema外键')
    return reference


def _validate_object_conditions(config):
    if 'objectInputConditions' not in config:
        return
    conditions = config['objectInputConditions']
    if (config.get('strategy') != 'GROUP_SUM' or not isinstance(conditions, list) or not conditions
            or any(not isinstance(row, dict) or set(row) != {'inputPath', 'operator'}
                   or row.get('operator') != 'IS_NULL' for row in conditions)):
        _fail('FACT_METADATA_CONFIG_INVALID', '对象来源条件仅允许分类规则显式配置正式字段IS_NULL判断')
    paths = []
    for condition in conditions:
        _registered_input_reference(condition['inputPath'])
        paths.append(tuple(condition['inputPath']))
    if len(paths) != len(set(paths)):
        _fail('FACT_METADATA_CONFIG_INVALID', '冻结对象条件不得重复声明同一正式字段')


def validate_metadata_configuration(config):
    _validate_object_conditions(config)
    bindings = config.get('metadataBindings')
    keys = config.get('groupKeys')
    if (not isinstance(bindings, list) or not bindings or not isinstance(keys, list) or not keys
            or any(not _name(key) for key in keys) or len(keys) != len(set(keys))):
        _fail('FACT_METADATA_CONFIG_INVALID', '分类汇总必须配置精确元数据绑定及无重复分组键')
    names = []
    for binding in bindings:
        if not isinstance(binding, dict) or not _name(binding.get('name')):
            _fail('FACT_METADATA_CONFIG_INVALID', '元数据输出名称必须精确且非空')
        names.append(binding['name'])
        kind = binding.get('sourceType')
        if kind == 'CONFIGURATION_VALUE':
            if set(binding) != {'name', 'sourceType', 'value'} or not _name(binding.get('value')):
                _fail('FACT_METADATA_CONFIG_INVALID', '分类常量必须由规则声明非空字符串')
        elif kind == 'FORMAL_OBJECT_REFERENCE':
            required = {'name', 'sourceType', 'inputPath', 'referenceModel', 'valueField'}
            reference = REGISTERED_REFERENCES.get(binding.get('referenceModel'))
            path = binding.get('inputPath')
            if (set(binding) != required or not reference
                    or not isinstance(path, list) or not path or any(not _name(part) for part in path)
                    or binding.get('valueField') not in reference['valueFields']):
                _fail('FACT_METADATA_CONFIG_INVALID', '只能配置注册的正式对象FK、明确字段路径及可公开身份字段')
            typed_reference = reference['inputReferences'].get(tuple(path))
            if not typed_reference:
                _fail('FACT_METADATA_CONFIG_INVALID', '对象输入路径必须对应已注册的正式外键，禁止用任意整数替代身份')
            field = typed_reference['sourceModel']._meta.get_field(typed_reference['sourceField'])
            if not isinstance(field, ForeignKey) or field.remote_field.model is not reference['model']:
                _fail('FACT_METADATA_CONFIG_INVALID', '注册对象引用必须与当前正式Schema外键类型一致')
        elif kind == 'FORMAL_FROZEN_VALUE':
            path = binding.get('inputPath')
            if (set(binding) != {'name', 'sourceType', 'inputPath'}
                    or not isinstance(path, list) or not path or any(not _name(part) for part in path)
                    or tuple(path) not in REGISTERED_FROZEN_VALUES):
                _fail('FACT_METADATA_CONFIG_INVALID', '冻结来源值只能绑定已注册的正式输入及来源证据路径')
        elif kind == 'FORMAL_SOURCE_IDENTITY':
            if (set(binding) != {'name', 'sourceType', 'valueField'}
                    or not _name(binding.get('valueField'))
                    or binding['valueField'] not in REGISTERED_SOURCE_IDENTITIES):
                _fail('FACT_METADATA_CONFIG_INVALID', '来源身份只能绑定已证明的正式来源FK字段')
        else:
            _fail('FACT_METADATA_CONFIG_INVALID', '元数据来源类型必须使用注册正式来源或配置值')
    aliases = [config[name] for name in ('quantityTraceKey', 'uomTraceKey', 'inputHashTraceKey') if name in config]
    if (len(names) != len(set(names)) or not set(keys).issubset(names)
            or any(not _name(alias) for alias in aliases)
            or len(aliases) != len(set(aliases))
            or (set(names) | set(aliases)) & RESERVED_TRACE_KEYS
            or set(names) & set(aliases)):
        _fail('FACT_METADATA_CONFIG_INVALID', '元数据、分组键与追溯别名不得重复或覆盖正式证据字段')
    if not any(row['sourceType'] in ('FORMAL_OBJECT_REFERENCE', 'FORMAL_FROZEN_VALUE',
                                   'FORMAL_SOURCE_IDENTITY') for row in bindings):
        _fail('FACT_METADATA_CONFIG_INVALID', '分类汇总至少需要一项来自冻结工程对象的正式来源证明')
    return bindings


def _input_path(obj, path):
    value = obj
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _present_path(obj, path):
    value = obj
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def _object_condition_proof(saved, item, config):
    result = []
    for condition in config['objectInputConditions']:
        registered = _registered_input_reference(condition['inputPath'])
        present, value = _present_path(saved, condition['inputPath'])
        snapshot_present, snapshot_value = _present_path(item.content_snapshot, registered['snapshotPath'])
        no_revision = (item.design_revision_id is None and isinstance(item.content_snapshot, dict)
                       and 'revision' in item.content_snapshot and item.content_snapshot['revision'] is None)
        if not snapshot_present and not no_revision:
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '对象条件的冻结正式修订字段不存在，缺字段不能当作NULL')
        if not present or canonical_json(value) != canonical_json(snapshot_value):
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '对象条件必须读取存在且一致的冻结正式引用字段')
        if value is not None and (type(value) is not int or value <= 0):
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '对象条件正式引用只能为NULL或精确正整数FK')
        result.append({'configuration': deepcopy(condition), 'inputValue': value,
                      'snapshotPath': list(registered['snapshotPath']), 'snapshotValue': snapshot_value,
                      'matched': value is None})
    return result


def _frozen_value_proof(binding, saved, item):
    registered = REGISTERED_FROZEN_VALUES[tuple(binding['inputPath'])]
    present, value = _present_path(saved, binding['inputPath'])
    field_proof = {'configuration': deepcopy(binding), 'inputValue': value, 'snapshotValues': []}
    if not present:
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结来源值的正式对象输入字段不存在', field=binding['name'])
    for path in registered['snapshotPaths']:
        snapshot_present, snapshot_value = _present_path(item.content_snapshot, path)
        if not snapshot_present or canonical_json(snapshot_value) != canonical_json(value):
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结来源原值、设计来源值与原核算输入不一致', field=binding['name'])
        field_proof['snapshotValues'].append({'path': list(path), 'value': deepcopy(snapshot_value)})
    if value is None or value == '':
        return value, field_proof
    if not _name(value):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结来源值必须为精确非空文本，不得标准化或猜测替代', field=binding['name'])
    evidence_present, evidence = _present_path(item.content_snapshot, registered['evidencePath'])
    sheet, row = saved.get('sourceSheet'), saved.get('sourceRow')
    if (not evidence_present or not isinstance(evidence, dict)
            or not {'cell', 'value', 'formula', 'sourceValueType'}.issubset(evidence)
            or not _name(sheet) or type(row) is not int or row <= 0
            or evidence['cell'] != f"{sheet}!{registered['evidenceColumn']}{row}"
            or canonical_json(evidence['value']) != canonical_json(value)
            or evidence['sourceValueType'] not in ('来源原始值', '来源派生值')
            or (evidence['formula'] is not None and not isinstance(evidence['formula'], str))):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结来源值必须具备同一对象的完整原单元格证据', field=binding['name'])
    field_proof.update({'evidencePath': list(registered['evidencePath']),
                        'sourceEvidence': deepcopy(evidence), 'sourceEvidenceHash': _digest(evidence),
                        'valueHash': _digest(value)})
    return value, field_proof


def _saved_object_input_matches(item, saved):
    """Check normalized business values against the pinned internal baseline.

    Sheet/row/import aliases remain in the hashed original input. They are
    provenance, not a current importer that must be replayed for consumption.
    """
    snapshot = item.content_snapshot
    design = snapshot.get('designItem', {})
    revision = snapshot.get('revision') or {}
    existing = design.get('existingDesignData') or {}
    effective = {**existing, **(revision.get('designData') or {})}
    expected = {'baselineItemId': item.pk, 'baselineContentHash': item.content_hash,
        'designItemId': item.design_item_id, 'designItemNo': item.item_no_snapshot,
        'sourceAttributeId': item.source_attribute_id, 'sourceRecordId': item.source_record_id,
        'inputAuthority': OBJECT_INPUT_AUTHORITY, 'revision': revision.get('revision'),
        'sourceVersion': item.source_version_snapshot, 'sourceContentHash': item.source_content_hash_snapshot}
    for key in ('physicalQuantity', 'physicalUomId', 'physicalUom', 'productCategoryId', 'productDefinitionId'):
        expected[key] = design.get(key)
    for key in ('designLength', 'designWidth', 'designThickness'):
        expected[key] = revision.get(key) if revision else effective.get(key)
    for key in ('designUomId', 'materialId', 'materialProcessTypeId', 'paintProcessTypeId', 'edgeMethodId'):
        expected[key] = revision.get(key)
    for key in ('visibleCondition', 'finishOrColor', 'paintProcess'):
        expected[key] = effective.get(key) or ''
    expected['routingProcessCode'] = existing.get('routingProcessCode') or ''
    expected['processConfigurationCode'] = effective.get('processConfigurationCode') or existing.get('routingProcessCode') or ''
    # A saved label resolved from a master ID need not be resolved again.
    # Where the baseline itself stores the label it remains an exact value.
    if effective.get('edgeMethod'):
        expected['edgeMethod'] = str(effective['edgeMethod'])
    return all(canonical_json(saved.get(key)) == canonical_json(value) for key, value in expected.items())


def _prepare_origin(origin, *, read_cache=None):
    """Validate the saved input and internal baseline without replaying import."""
    from .engineering_calculation_service import EngineeringCalculationError
    from .formal_engineering_continuation_service import (
        _baseline_reference, calculation_input_hash,
    )
    from .engineering_workbook_source_service import saved_workbook_input, WorkbookSourceError
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, origin.company_id)

    trace = origin.trace if isinstance(origin.trace, dict) else {}
    reference, objects, source_reference = (trace.get('baselineReference'),
        trace.get('objectInputSnapshot'), trace.get('sourceReference'))
    if (not isinstance(reference, dict) or not isinstance(objects, list) or not objects
            or not isinstance(source_reference, dict)
            or type(reference.get('id')) is not int):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '分类输入缺少原核算保存的正式基线及对象快照')
    try:
        frozen_hash = calculation_input_hash(reference, objects,
            **saved_workbook_input(origin, reference, objects, read_cache=cache))
    except (EngineeringCalculationError, WorkbookSourceError) as exc:
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '原核算输入合同或正式工作簿来源证明不一致', cause=exc.code)
    source = origin.source_record
    graph, results = trace.get('ruleGraphSnapshot'), trace.get('resultSnapshot')
    if (not isinstance(graph, list) or not graph or not isinstance(results, list) or not results
            or _digest(graph) != origin.rule_graph_hash
            or _digest(results) != origin.result_hash or trace.get('resultHash') != origin.result_hash):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '原核算保存的规则图、结果快照与独立Hash证明不一致')
    if (frozen_hash != origin.input_hash or frozen_hash != trace.get('objectInputSnapshotHash')
            or source_reference.get('id') != source.pk
            or source.company_id != origin.company_id
            or source_reference.get('sourceVersion') != source.source_version
            or source_reference.get('contentHash') != source.content_hash):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '原对象输入Hash或来源工程版本证明不一致')
    baseline = _read_once(cache, ('metadata_baseline_row', origin.company_id, reference['id']), lambda:
        OrderEngineeringBaseline.objects.select_related('sales_order').filter(pk=reference['id']).first())
    if (not baseline or baseline.company_id != origin.company_id or production_status(baseline) != 'confirmed'
            or baseline.sales_order_id != origin.sales_order_item.sales_order_id):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '原核算必须引用同公司同订单的已确认工程基线')
    items = _read_once(cache, ('metadata_baseline_items', origin.company_id, baseline.pk,
        origin.sales_order_item_id), lambda: list(baseline.items.select_related('design_item', 'source_record', 'source_attribute')
        .defer('source_record__source_payload', 'design_item__original_requirement',
               'design_item__existing_design_data', 'design_item__match_results', 'source_attribute__raw_value')
        .filter(design_item__sales_order_item_id=origin.sales_order_item_id)
        .order_by('source_attribute_id', 'design_item_id', 'pk')))
    if not items or len(items) != len(objects):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '基线对象范围与原核算冻结范围不一致')
    by_item, by_object = {}, {}
    try:
        if _baseline_reference(baseline, items, read_cache=cache) != reference:
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '完整工程基线或实例子集Hash与原核算不一致')
        for item, envelope in zip(items, objects):
            saved = envelope.get('input') if isinstance(envelope, dict) else None
            revision = item.content_snapshot.get('revision') if isinstance(item.content_snapshot, dict) else None
            if ((item.design_revision_id is not None and (not isinstance(revision, dict)
                    or type(revision.get('id')) is not int or revision['id'] != item.design_revision_id))
                    or (item.design_revision_id is None and isinstance(revision, dict) and revision.get('id') is not None)):
                _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结设计修订身份必须精确等于基线正式修订外键')
            if (item.source_record_id != source.pk or not isinstance(saved, dict)
                    or item.source_version_snapshot != source_reference['sourceVersion']
                    or item.source_content_hash_snapshot != source_reference['contentHash']
                    or _digest(item.content_snapshot) != item.content_hash
                    or item.design_item.company_id != origin.company_id
                    or item.design_item.source_record_id != source.pk
                    or item.design_item.source_attribute_id != item.source_attribute_id
                    or item.source_attribute.sales_order_item_id != origin.sales_order_item_id
                    or not _saved_object_input_matches(item, saved)
                    or saved.get('inputAuthority') != OBJECT_INPUT_AUTHORITY
                    or envelope.get('baselineItemId') != item.pk
                    or envelope.get('designItemId') != item.design_item_id
                    or envelope.get('sourceAttributeId') != item.source_attribute_id
                    or envelope.get('contentHash') != item.content_hash
                    or envelope.get('sourceVersion') != source_reference['sourceVersion']
                    or envelope.get('sourceContentHash') != source_reference['contentHash']):
                _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结对象输入与基线内容、正式来源FK或Hash不一致')
            if item.pk in by_item or item.design_item_id in by_object:
                _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结工程对象身份重复')
            by_item[item.pk] = item
            by_object[item.design_item_id] = envelope
    except EngineeringCalculationError as exc:
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结工程对象证明读取失败', cause=exc.code)
    return {'baseline': baseline, 'byItem': by_item, 'byObject': by_object, 'inputHash': frozen_hash,
        'sourceReference': deepcopy(source_reference)}


def resolve_metadata(*, origin, fact, config, cache=None):
    """Return classified data or an explicit missing list, with frozen provenance."""
    bindings = validate_metadata_configuration(config)
    cache = {} if cache is None else cache
    if origin.pk not in cache:
        cache[origin.pk] = _prepare_origin(origin)
    context = cache[origin.pk]
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    if any(type(trace.get(key)) is not int or trace[key] <= 0 for key in
            ('baselineId', 'baselineItemId', 'designItemId', 'sourceAttributeId')):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '原事实工程对象血缘必须使用精确正式正整数身份')
    item = context['byItem'].get(trace.get('baselineItemId'))
    envelope = context['byObject'].get(trace.get('designItemId'))
    saved = envelope.get('input') if envelope else None
    detail_input = fact.source_detail.input_snapshot if fact.source_detail_id else None
    if (not item or not envelope or item.design_item_id != trace.get('designItemId')
            or trace.get('baselineId') != context['baseline'].pk
            or trace.get('baselineContentHash') != item.content_hash
            or trace.get('sourceAttributeId') != item.source_attribute_id
            or not isinstance(detail_input, dict)
            or canonical_json(detail_input.get('object')) != canonical_json(saved)):
        _fail('FACT_METADATA_SOURCE_UNPROVEN', '成功明细、原事实与冻结工程对象身份或输入不一致')
    proof = {'contractVersion': CONTRACT, 'sourceFactId': fact.pk,
        'sourceCalculationId': origin.pk, 'sourceDetailId': fact.source_detail_id,
        'objectInputHash': context['inputHash'], 'baselineId': context['baseline'].pk,
        'baselineItemId': item.pk, 'baselineContentHash': item.content_hash,
        'designItemId': item.design_item_id, 'designRevisionId': item.design_revision_id,
        'sourceAttributeId': item.source_attribute_id, 'sourceRecordId': origin.source_record_id,
        'sourceRecordVersion': context['sourceReference']['sourceVersion'],
        'sourceRecordHash': context['sourceReference']['contentHash'],
        'frozenObjectInput': deepcopy(saved), 'bindings': []}
    metadata, missing, references = {}, [], {}
    if 'objectInputConditions' in config:
        conditions = _object_condition_proof(saved, item, config)
        proof['objectInputConditions'] = conditions
        if not all(row['matched'] for row in conditions):
            proof.update({'metadata': {}, 'missing': []})
            return {'metadata': {}, 'missing': [], 'proof': proof, 'excluded': True}
    for binding in bindings:
        name = binding['name']
        if binding['sourceType'] == 'CONFIGURATION_VALUE':
            metadata[name] = binding['value']
            proof['bindings'].append({'configuration': deepcopy(binding), 'value': binding['value']})
            continue
        if binding['sourceType'] == 'FORMAL_SOURCE_IDENTITY':
            value = proof[binding['valueField']]
            if type(value) is not int or value <= 0:
                _fail('FACT_METADATA_SOURCE_UNPROVEN', '正式来源身份必须为已证明的精确正整数FK', field=name)
            metadata[name] = value
            proof['bindings'].append({'configuration': deepcopy(binding), 'inputValue': value,
                                      'sourceIdentity': {'valueField': binding['valueField'], 'value': value}})
            continue
        if binding['sourceType'] == 'FORMAL_FROZEN_VALUE':
            value, field_proof = _frozen_value_proof(binding, saved, item)
            if value is None or value == '':
                missing.append({'name': name, 'reasonCode': 'FORMAL_FROZEN_VALUE_NOT_MAINTAINED'})
            else:
                metadata[name] = value
            proof['bindings'].append(field_proof)
            continue
        raw_id = _input_path(saved, binding['inputPath'])
        registered = REGISTERED_REFERENCES[binding['referenceModel']]
        typed_reference = registered['inputReferences'][tuple(binding['inputPath'])]
        if canonical_json(raw_id) != canonical_json(_input_path(item.content_snapshot, typed_reference['snapshotPath'])):
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结对象输入引用与正式修订快照外键值不一致', field=name)
        field_proof = {'configuration': deepcopy(binding), 'inputValue': raw_id}
        if raw_id is None or raw_id == '':
            missing.append({'name': name, 'reasonCode': 'FORMAL_REFERENCE_NOT_MAINTAINED'})
        elif type(raw_id) is not int or raw_id <= 0:
            _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结输入正式引用必须为正整数FK', field=name)
        else:
            key = (binding['referenceModel'], raw_id)
            if key not in references:
                references[key] = registered['model'].objects.filter(pk=raw_id).first()
            row = references[key]
            if row is None:
                missing.append({'name': name, 'reasonCode': 'FORMAL_REFERENCE_MISSING', 'referenceId': raw_id})
            elif getattr(row, registered['companyField']) != origin.company_id:
                _fail('FACT_METADATA_SOURCE_UNPROVEN', '冻结工艺引用跨公司', field=name)
            elif not getattr(row, registered['activeField']):
                missing.append({'name': name, 'reasonCode': 'FORMAL_REFERENCE_INACTIVE', 'referenceId': raw_id})
            else:
                value = getattr(row, binding['valueField'])
                if not ((type(value) is int and value > 0) or _name(value)):
                    missing.append({'name': name, 'reasonCode': 'FORMAL_REFERENCE_VALUE_MISSING', 'referenceId': raw_id})
                else:
                    metadata[name] = value
                field_proof['referenceSnapshot'] = {'model': binding['referenceModel'],
                    'id': row.pk, 'companyId': row.company_id, 'isActive': row.is_active,
                    'code': row.code, 'valueField': binding['valueField'], 'value': value}
        proof['bindings'].append(field_proof)
    proof['metadata'] = deepcopy(metadata)
    proof['missing'] = deepcopy(missing)
    result = {'metadata': metadata, 'missing': missing, 'proof': proof}
    if 'objectInputConditions' in config:
        result['excluded'] = False
    return result


def metadata_trace(context, config, *, uom_code):
    """Expose only configured aliases; all values remain part of proven output."""
    result = {**context['metadata'], 'metadata': deepcopy(context['metadata']), 'inputHash': context['inputHash']}
    for option, value in (
        ('quantityTraceKey', context['result']['value']),
        ('uomTraceKey', uom_code), ('inputHashTraceKey', context['inputHash']),
    ):
        if option in config:
            result[config[option]] = value
    return result
