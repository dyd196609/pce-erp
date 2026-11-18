"""Explicit fact/rule orchestration with a proved, classified quantity readback.

The existing services remain the sole writers of facts, rules and EOR. Group
names, business classifications, arithmetic and process references are data.
"""
from copy import deepcopy
from decimal import Decimal

from django.db import transaction

from .engineering_fact_extension_service import EngineeringFactExtensionService, validate_extension_fact
from .manufacturing_configuration_service import ManufacturingConfigurationService
from .models import EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringRuleDefinition
from .operation_requirement_service import _authorize, _fail, VIEW


CONTRACT = 'PCE-CLASSIFIED-FACT-EOR-BATCH-V1'


class ManufacturingFactBatchService:
    @classmethod
    @transaction.atomic
    def consolidated_readback(cls, *, user, calculation_ids, group_keys):
        _authorize(user, VIEW)
        if (not isinstance(calculation_ids, list) or len(calculation_ids) != len(set(calculation_ids))
                or any(type(pk) is not int or pk <= 0 for pk in calculation_ids)
                or not isinstance(group_keys, list) or not group_keys
                or len(group_keys) != len(set(group_keys))
                or any(not isinstance(key, str) or not key.strip() or key != key.strip() for key in group_keys)):
            _fail('CLASSIFIED_READBACK_SCOPE_INVALID', '分类回读必须声明精确无重复的核算ID及分组字段')
        groups, read_cache = {}, {}
        for pk in calculation_ids:
            calc = EngineeringCalculationRecord.objects.select_related('source_record', 'origin_calculation').filter(
                pk=pk, company_id=user.company_id, scope='fact_extension', status='completed').first()
            if not calc:
                _fail('CLASSIFIED_READBACK_SCOPE_INVALID', '分类回读仅接受同公司已完成的正式事实增量')
            facts = list(EngineeringDerivedFact.objects.filter(calculation=calc).select_related('source_detail__rule', 'uom'))
            if not facts:
                _fail('CLASSIFIED_READBACK_SCOPE_INVALID', '分类增量缺少正式输出')
            validate_extension_fact(calc, facts[-1], read_cache=read_cache)
            base = calc.origin_calculation
            baseline_id = base.trace.get('baselineReference', {}).get('id')
            for fact in facts:
                config = fact.source_detail.rule.specification.get('factExtension', {})
                if config.get('strategy') != 'GROUP_SUM':
                    continue
                if config.get('groupKeys') != group_keys:
                    _fail('CLASSIFIED_READBACK_SCOPE_INVALID', '回读分组必须精确等于已发布分类汇总规则')
                values = [fact.trace.get(key) for key in group_keys]
                if any(not ((type(value) is int and value > 0)
                           or (isinstance(value, str) and value.strip() and value == value.strip())) for value in values):
                    _fail('CLASSIFIED_READBACK_SCOPE_INVALID', '已发布分类字段缺失或无效')
                identity = (calc.source_record_id, calc.source_record.source_version,
                            calc.source_record.content_hash, baseline_id, fact.uom_id, *values)
                row = groups.setdefault(identity, {'sourceRecordId': calc.source_record_id,
                    'sourceRecordVersion': calc.source_record.source_version,
                    'sourceRecordHash': calc.source_record.content_hash, 'baselineId': baseline_id,
                    'group': dict(zip(group_keys, values)), 'uomId': fact.uom_id, 'uomCode': fact.uom.code,
                    'quantity': Decimal(0), 'factIds': [], 'sourceFactIds': [], 'partitions': []})
                inputs = list(fact.inputs.order_by('sequence'))
                source_ids = [link.source_fact_id for link in inputs]
                if len(source_ids) != len(set(source_ids)) or set(source_ids) & set(row['sourceFactIds']):
                    _fail('CLASSIFIED_FACT_DUPLICATE_SOURCE', '同一正式工艺分组不得重复汇总来源事实')
                row['quantity'] += Decimal(fact.value['decimal'])
                row['factIds'].append(fact.pk)
                row['sourceFactIds'].extend(source_ids)
                row['partitions'].append({'factId': fact.pk, 'calculationId': calc.pk,
                    'baseEngineeringCalculationId': base.pk, 'engineeringInstanceId': calc.engineering_instance_id,
                    'salesOrderItemId': calc.sales_order_item_id, 'quantity': fact.value['decimal'],
                    'sourceFactIds': source_ids, 'ruleId': fact.rule_id,
                    'ruleVersion': fact.source_detail.rule_version, 'inputHash': calc.input_hash,
                    'outputHash': fact.trace['outputHash']})
        result = []
        for row in groups.values():
            row['quantity'] = str(row['quantity'])
            result.append(row)
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'groups': result,
                'businessWriteCount': 0, 'auditWriteCount': 0}

    @classmethod
    @transaction.atomic
    def execute(cls, *, user, fact_package, manufacturing_package, source_calculation_ids,
                request_key, reason, allow_partial=False):
        if (not isinstance(source_calculation_ids, list) or not source_calculation_ids
                or len(source_calculation_ids) != len(set(source_calculation_ids))
                or any(type(pk) is not int or pk <= 0 for pk in source_calculation_ids)
                or not isinstance(request_key, str) or not request_key.strip()
                or not isinstance(reason, str) or not reason.strip() or type(allow_partial) is not bool):
            _fail('CLASSIFIED_BATCH_SCOPE_INVALID', '分类承接必须声明精确来源集合、办理依据及幂等键')
        configured = EngineeringFactExtensionService.configure(user=user, package=fact_package, reason=reason)
        previews = [EngineeringFactExtensionService.preview(user=user, source_calculation_id=pk,
            rule_ids=configured['ruleIds']) for pk in source_calculation_ids]
        missing = [row for preview in previews for row in preview['retainedMissingMetadata']]
        if missing and not allow_partial:
            _fail('CLASSIFIED_METADATA_REQUIRED', '部分来源缺正式分类，必须明确保留部分覆盖才可承接有效来源', missingCount=len(missing))
        manufacturing = deepcopy(manufacturing_package)
        for row in manufacturing['rules']:
            selector = row['specification']['manufacturing']['sourceSelector']
            code = selector.pop('producerRuleCode', None)
            if code:
                producer = EngineeringRuleDefinition.objects.filter(company_id=user.company_id,
                    rule_code=code, version=selector['producerRuleVersion'], status='released').first()
                if not producer:
                    _fail('FACT_RULE_NOT_RELEASED', '制造配置引用的精确分类生产规则未发布')
                selector['producerRuleId'] = producer.pk
        resources = ManufacturingConfigurationService.configure(user=user, package=manufacturing, reason=reason)
        rules = [row['id'] for row in resources['rules']]
        runs, calculations, unmapped = [], [], []
        for pk in source_calculation_ids:
            derived = EngineeringFactExtensionService.derive(user=user, source_calculation_id=pk,
                rule_ids=configured['ruleIds'], idempotency_key=f'{request_key}:{pk}', reason=reason)
            generated = None
            if derived.get('calculationId'):
                generated = ManufacturingConfigurationService.generate_for_calculation(user=user,
                    source_calculation_id=derived['calculationId'], request_key=request_key,
                    reason=reason, rule_ids=rules)
                mapping_gap_only = (bool(generated['blockers']) and all(
                    row['code'] == 'MANUFACTURING_INPUT_MAPPING_MISSING' for row in generated['blockers']))
                if generated['blockers'] and not (allow_partial and mapping_gap_only):
                    _fail('CLASSIFIED_EOR_BLOCKED', '正式制造配置未能完整承接已分类来源', blockers=generated['blockers'])
                consumed = {row['sourceFactId'] for row in generated['requirements']}
                consumed.update(row['sourceFactId'] for row in generated['retainedZeroFacts'])
                for fact in EngineeringDerivedFact.objects.filter(pk__in=derived['factIds']).select_related('source_detail__rule'):
                    if fact.pk in consumed:
                        continue
                    unmapped.append({'sourceFactId': fact.pk, 'sourceCalculationId': fact.calculation_id,
                        'baseEngineeringCalculationId': pk, 'quantity': fact.value['decimal'], 'uomId': fact.uom_id,
                        'group': fact.trace.get('group'), 'ruleId': fact.rule_id,
                        'ruleVersion': fact.source_detail.rule_version,
                        'reasonCode': 'MANUFACTURING_INPUT_MAPPING_MISSING'})
                if unmapped and not allow_partial:
                    _fail('CLASSIFIED_EOR_MAPPING_REQUIRED', '部分已分类事实缺具体工序规则，禁止把部分承接声明为完整')
                calculations.append(derived['calculationId'])
            runs.append({'baseEngineeringCalculationId': pk, 'derivation': derived, 'generation': generated})
        keys = fact_package.get('consolidatedReadback', {}).get('groupKeys')
        summary = cls.consolidated_readback(user=user, calculation_ids=calculations, group_keys=keys)
        return {'contractVersion': CONTRACT, 'factConfiguration': configured,
            'manufacturingConfiguration': resources, 'runs': runs, 'consolidatedFacts': summary,
            'retainedMissingMetadata': missing, 'retainedUnmappedFacts': unmapped,
            'coverageStatus': 'PARTIAL' if missing or unmapped else 'COMPLETE',
            'statusLabel': '有效来源已承接，其他来源缺正式分类或工序规则' if missing or unmapped else '分类事实与工序需求承接完成',
            'factSource': 'server', 'productionPlanWriteCount': 0, 'apsWriteCount': 0}
