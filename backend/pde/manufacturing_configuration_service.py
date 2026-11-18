"""Audited configuration packages over the existing engineering rule model.

Packages contain all business mappings. This module knows no field, product,
Process name, order number or unit conversion. EOR writes use the sole existing
OperationRequirementService. Missing business inputs remain explicit blockers.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from django.db import transaction
from system.models import Company
from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)
from .engineering_rule_foundation import canonical_json, validate_specification
from .models import (ManufacturingMode, EngineeringRuleDefinition, EngineeringDerivedFact,
                     EngineeringCalculationRecord, CapacityProductType)
from .operation_requirement_service import (_authorize, _executor, _fail, _requirement_fact,
    OperationRequirementError, OperationRequirementService, VIEW)
from .production_foundation_service import _audit, _snapshot
from .manufacturing_rule_configuration import publication_config_validation, configured_source_candidate, CONTRACT

CREATE = 'production.engineering.rule.create'
RELEASE = 'production.engineering.rule.release'


def _date(value):
    return date.fromisoformat(value) if value else None


def _audit_state(user, obj, before, after, permission, decision, chain, reason, package_hash):
    return _audit(user=user, organization_id=user.company_id, action_code=permission,
        instance=obj, before=before, after=after, reason=reason, authorization=decision,
        execution_chain=chain, audit_context={'contractVersion': CONTRACT, 'packageHash': package_hash})


def _create_released(model, fields, *, user, decisions, chain, reason, package_hash):
    obj = create_business_object_with_initial_state(model=model, initial_state='draft', **fields)
    audit = _audit_state(user, obj, {'status': ''}, _snapshot(obj), CREATE, decisions[CREATE], chain, reason, package_hash)
    record_projected_business_transition(object_type=model.__name__, object_id=obj.pk, source_state='',
        target_state='draft', action_code=CREATE, operator=user, reason=reason,
        audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}', allowed_transitions=(('', 'draft'),))
    for source, target in (('draft', 'reviewed'), ('reviewed', 'released')):
        if model is EngineeringRuleDefinition:
            publication_config_validation(obj, require_released=False)
        audit = _audit_state(user, obj, _snapshot(obj), {**_snapshot(obj), 'status': target},
                             RELEASE, decisions[RELEASE], chain, reason, package_hash)
        transition_business_object(business_object=obj, object_type=model.__name__, source_state=source,
            target_state=target, action_code=RELEASE, operator=user, reason=reason,
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
            allowed_transitions=((source, target),), version_field=None)
    return obj


class ManufacturingConfigurationService:
    @classmethod
    @transaction.atomic
    def configure(cls, *, user, package, reason):
        if not isinstance(package, dict) or package.get('contractVersion') != CONTRACT or not str(reason).strip():
            _fail('MANUFACTURING_PACKAGE_INVALID', '必须提供正式配置包合同及办理原因')
        if package.get('companyId') != user.company_id:
            _fail('ORGANIZATION_MISMATCH', '配置包必须属于办理人当前公司')
        decisions = {permission: _authorize(user, permission) for permission in (CREATE, RELEASE)}
        chain = _executor(user)
        Company.objects.select_for_update().get(pk=user.company_id)
        package_hash = sha256(canonical_json(package).encode()).hexdigest()
        mode_rows, rule_rows = [], []
        for row in package.get('modes', []):
            fields = dict(company_id=user.company_id, code=row['code'], name=row['name'], version=row['version'],
                uom_id=row['uomId'], effective_from=_date(row.get('effectiveFrom')), effective_to=_date(row.get('effectiveTo')))
            obj = ManufacturingMode.objects.filter(company_id=user.company_id, code=row['code'], version=row['version']).first()
            if obj:
                if obj.status != 'released' or any(getattr(obj, key) != value for key, value in fields.items()):
                    _fail('MANUFACTURING_VERSION_CONFLICT', '已存在的模式版本与配置包不一致，必须建立新版本')
            else:
                obj = _create_released(ManufacturingMode, fields, user=user, decisions=decisions,
                                       chain=chain, reason=reason, package_hash=package_hash)
            mode_rows.append({'id': obj.pk, 'code': obj.code, 'version': obj.version})
        for row in package.get('rules', []):
            spec = deepcopy(row['specification'])
            composition = spec.get('ruleRole') == 'OPERATION_ALLOCATION_COMPOSITION'
            if not composition:
                config = spec.get('manufacturing', {})
                mode = ManufacturingMode.objects.filter(company_id=user.company_id, code=config.pop('modeCode', None),
                                                          version=config.get('modeVersion'), status='released').first()
                if not mode:
                    _fail('MANUFACTURING_MODE_MISSING', '配置规则未引用同公司已发布的精确制造模式版本')
                config['modeId'] = mode.pk
            validate_specification(spec)
            fields = dict(company_id=user.company_id, rule_code=row['ruleCode'], rule_name=row['ruleName'],
                version=row['version'], rule_kind=row.get('ruleKind', 'formula'), specification=spec,
                effective_from=_date(row.get('effectiveFrom')), effective_to=_date(row.get('effectiveTo')))
            if composition:
                from .operation_contribution_composition import (
                    OperationContributionCompositionError, validate_composition_references,
                )
                if fields['rule_kind'] != 'decision':
                    _fail('ALLOCATION_COMPOSITION_INVALID', '投产量组合声明必须使用正式判断规则类型。')
                try:
                    validate_composition_references(EngineeringRuleDefinition(**fields))
                except OperationContributionCompositionError as exc:
                    _fail(exc.code, exc.message, **exc.details)
            obj = EngineeringRuleDefinition.objects.filter(company_id=user.company_id, rule_code=row['ruleCode'], version=row['version']).first()
            if obj:
                if obj.status != 'released' or any(getattr(obj, key) != value for key, value in fields.items()):
                    _fail('MANUFACTURING_VERSION_CONFLICT', '已存在规则版本与配置包不一致；禁止覆盖')
                publication_config_validation(obj, require_released=True)
            else:
                candidate = EngineeringRuleDefinition(**fields)
                publication_config_validation(candidate, require_released=False)
                obj = _create_released(EngineeringRuleDefinition, fields, user=user, decisions=decisions,
                                       chain=chain, reason=reason, package_hash=package_hash)
            rule_rows.append({'id': obj.pk, 'code': obj.rule_code, 'version': obj.version})
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'packageHash': package_hash,
                'manufacturingModes': mode_rows, 'rules': rule_rows, 'pendingRules': package.get('pendingRules', [])}

    @classmethod
    @transaction.atomic
    def generate_for_calculation(cls, *, user, source_calculation_id, request_key, reason, rule_ids=None):
        _authorize(user, VIEW)
        origin = EngineeringCalculationRecord.objects.filter(pk=source_calculation_id,
            company_id=user.company_id, scope__in=('order_engineering', 'fact_extension'), status='completed').first()
        if not origin:
            _fail('SOURCE_CALCULATION_MISSING', '必须选择同公司完成的正式工程核算')
        facts = list(EngineeringDerivedFact.objects.filter(calculation=origin).select_related('source_detail__rule'))
        if origin.scope == 'fact_extension':
            from .engineering_fact_extension_service import validate_extension_fact
            if not facts:
                _fail('FACT_EXTENSION_UNPROVEN', '增量运行必须具有真实计算输出')
            validate_extension_fact(origin, facts[-1])
        instance = origin.engineering_instance
        types = set(CapacityProductType.objects.filter(company_id=user.company_id,
            product_category_id=instance.product_category_id,
            manufacturing_process_type_id=instance.selected_process_type_id).values_list('pk', flat=True))
        query = EngineeringRuleDefinition.objects.filter(company_id=user.company_id, status='released')
        if rule_ids is not None:
            if (not isinstance(rule_ids, list) or not rule_ids or any(type(pk) is not int or pk <= 0 for pk in rule_ids)
                    or len(rule_ids) != len(set(rule_ids))):
                _fail('MANUFACTURING_RULE_SCOPE_INVALID', '必须选择非空、精确且不重复的正式发布规则ID')
            query = query.filter(pk__in=rule_ids)
        rules = list(query)
        if rule_ids is not None and len(rules) != len(rule_ids):
            _fail('MANUFACTURING_RULE_SCOPE_INVALID', '所选发布规则缺失、未发布或不属于当前公司')
        from .operation_workload_source_service import (
            _SourceSchemeBatch, check_source_scheme_generation, OperationWorkloadSourceError,
        )
        batch = _SourceSchemeBatch(user, [row.pk for row in rules])
        selected_rules, applied_groups = [], []
        for rule in rules:
            output = (rule.specification.get('outputs') or [{}])[0]
            if output.get('productTypeId') not in types:
                selected_rules.append(rule)
                continue
            try:
                group = check_source_scheme_generation(user=user, rule=rule, batch=batch)
            except OperationWorkloadSourceError as error:
                if error.code in {'WORKLOAD_SOURCE_SCHEME_NOT_SELECTED', 'WORKLOAD_SOURCE_SELECTION_SCOPE_REQUIRED'} and rule_ids is None:
                    continue
                _fail(error.code, error.message, **error.details)
            if group:
                if not group <= batch.rule_ids:
                    _fail('WORKLOAD_SOURCE_SCHEME_GROUP_REQUIRED', '必须完整办理已应用方案全部成员')
                applied_groups.append(group)
            selected_rules.append(rule)
        rules = selected_rules
        for group in applied_groups:
            for rule in (row for row in rules if row.pk in group):
                selector = rule.specification.get('manufacturing', {}).get('sourceSelector', {})
                if not any(configured_source_candidate(selector=selector, fact=fact) for fact in facts):
                    _fail('WORKLOAD_SOURCE_SCHEME_INPUT_INCOMPLETE', '已应用完整方案有成员缺少当前正式来源事实，未办理任何成员')
        results, blockers, retained = [], [], []
        business_writes = audit_writes = 0
        for rule in rules:
            config = rule.specification.get('manufacturing') if isinstance(rule.specification, dict) else None
            if not isinstance(config, dict) or config.get('contractVersion') != CONTRACT:
                continue
            outputs = rule.specification.get('outputs', [])
            if len(outputs) != 1 or outputs[0].get('productTypeId') not in types:
                continue
            selector = config.get('sourceSelector', {})
            for fact in facts:
                if not configured_source_candidate(selector=selector, fact=fact):
                    continue
                try:
                    result = OperationRequirementService.generate(user=user, source_calculation_id=origin.pk,
                        source_fact_id=fact.pk, rule_id=rule.pk,
                        idempotency_key=sha256(f'{request_key}:{origin.pk}:{fact.pk}:{rule.pk}'.encode()).hexdigest(),
                        reason=reason, **({'_source_scheme_batch': batch} if applied_groups else {}))
                    results.append(result['operationRequirement'])
                    business_writes += result['businessWriteCount']
                    audit_writes += result['auditWriteCount']
                except OperationRequirementError as exc:
                    if exc.code == 'SOURCE_QUANTITY_INVALID':
                        try:
                            zero = isinstance(fact.value, dict) and Decimal(str(fact.value.get('decimal'))) == 0
                        except (InvalidOperation, TypeError, ValueError):
                            zero = False
                        if zero:
                            retained.append({'sourceFactId': fact.pk, 'ruleId': rule.pk,
                                'quantity': '0', 'statusLabel': '来源工程量为零；保留工程事实，无正工序需求'})
                            continue
                    blockers.append({'sourceFactId': fact.pk, 'ruleId': rule.pk, 'code': exc.code, 'statusLabel': exc.message})
        if not results and not blockers and not retained:
            blockers.append({'code': 'MANUFACTURING_INPUT_MAPPING_MISSING',
                'statusLabel': '当前核算没有精确匹配的已发布制造工序规则；未生成需求'})
        if applied_groups and blockers:
            # The selected scheme is one business choice. A failed member must
            # not leave a partly applied group behind in the original writer.
            transaction.set_rollback(True)
            results, business_writes, audit_writes = [], 0, 0
        return {'contractVersion': CONTRACT, 'factSource': 'server', 'sourceCalculationId': origin.pk,
                'statusLabel': '生成及来源校验完成' if results and not blockers else '工序需求未完整生成',
                'requirements': results, 'blockers': blockers, 'retainedZeroFacts': retained,
                'sourceFactCount': len(facts), 'businessWriteCount': business_writes,
                'auditWriteCount': audit_writes, 'sourceCalculationWriteCount': 0,
                'productionPlanWriteCount': 0}
