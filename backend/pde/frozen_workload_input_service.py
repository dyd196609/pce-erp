"""Fail-closed frozen test input adapter; mappings live in governed rule specs."""
from decimal import Decimal
from .order_routing_execution_service import _load, fail, baseline_for
from .models import EngineeringCalculationDetail, EngineeringRuleDefinition, OrderEngineeringBaselineItem, RoutingStep
from .engineering_rule_foundation import evaluate_specification, specification_hash
from .design_revision_approval_service import digest

CONTRACT='PCE-FROZEN-TEST-INPUT-V1'

def preview(*, user, arrangement_id, expected_revision, expected_edit_version, step_id, baseline_item_id, component_key, rule_id):
    arrangement,bom,root,chain=_load(user,arrangement_id,False)
    if arrangement.usage_purpose!='TEST_BUSINESS' or root.usage_purpose!='TEST_BUSINESS': fail('TEST_PURPOSE_REQUIRED','此链仅支持测试用途')
    if arrangement.arrangement_revision!=expected_revision or arrangement.edit_version!=expected_edit_version: fail('ARRANGEMENT_STALE','安排修订或编辑序号已变化')
    step=RoutingStep.objects.filter(pk=step_id,routing_version_id=arrangement.routing_version_id).first()
    if step is None: fail('STANDARD_STEP_REQUIRED','必须引用准确固定步骤')
    decision=arrangement.decisions.filter(routing_step=step,baseline_item_id=baseline_item_id).first() or arrangement.decisions.filter(routing_step=step,baseline_item__isnull=True).first()
    if decision is None or decision.decision!='REQUIRED': fail('EXECUTION_NOT_REQUIRED','该步骤未保存为执行')
    item=OrderEngineeringBaselineItem.objects.filter(pk=baseline_item_id,baseline=baseline_for(root)).first()
    if item is None: fail('ORDER_OBJECT_SCOPE_INVALID','对象不属于固定冻结基线')
    from .test_calculation_persistence import read_record
    read_record(user, root.pk)  # native immutable calculation/baseline readback proof
    components=item.content_snapshot.get('revision',{}).get('designData',{}).get('calculationInputs',{}).get('components',[])
    rule=EngineeringRuleDefinition.objects.filter(pk=rule_id,company_id=root.company_id,status='released').first()
    if rule is None: fail('RULE_REQUIRED','规则须经正式维护并已发布')
    from .operation_requirement_service import _active
    if not _active(rule): fail('RULE_NOT_EFFECTIVE','规则已过有效期')
    spec=rule.specification; mapping=spec.get('frozenTestInput')
    if not isinstance(mapping,dict) or mapping.get('contractVersion')!=CONTRACT: fail('FROZEN_MAPPING_REQUIRED','缺少已维护的冻结测试字段映射；不得按字段名或规则ID推断')
    if mapping.get('quantityBasis')!='SOURCE_SCOPE_TOTAL' or mapping.get('operationId')!=step.operation_id: fail('MAPPING_SCOPE_INVALID','数量口径与准确步骤工序不匹配')
    product_scope=mapping.get('productScope')
    if product_scope is not None:
        route=arrangement.routing_version.routing
        if (not isinstance(product_scope,dict) or set(product_scope)!={'productCategoryId','manufacturingProcessTypeId'}
                or any(type(v) is not int or v<=0 for v in product_scope.values())
                or product_scope!={'productCategoryId':route.product_category_id,'manufacturingProcessTypeId':route.manufacturing_process_type_id}):
            fail('MAPPING_PRODUCT_SCOPE_INVALID','冻结测试映射不适用于固定路线的产品分类及工艺范围')
    aggregate=mapping.get('scopeMode')=='BASELINE_ITEM_TOTAL'
    if aggregate:
        if component_key or mapping.get('usagePurpose')!='TEST_BUSINESS': fail('COMPONENT_SCOPE_INVALID','范围汇总只允许明确测试用途与整个冻结对象范围')
        selector=mapping.get('componentSelector')
        selected=components
        if selector is not None:
            if not isinstance(selector,dict) or set(selector)!={'field','values'} or selector['field'] not in ('name','key') or not isinstance(selector['values'],list) or not selector['values']: fail('COMPONENT_SELECTOR_INVALID','部件筛选须为受治理冻结属性的明确枚举')
            selected=[x for x in components if x.get(selector['field']) in selector['values']]
            if {x.get(selector['field']) for x in selected}!=set(selector['values']): fail('COMPONENT_SCOPE_INVALID','受治理部件筛选存在未匹配值')
        keys=[x.get('key') for x in selected]
        if not keys or any(not k for k in keys) or len(set(keys))!=len(keys): fail('FROZEN_SCOPE_INVALID','冻结部件范围缺失或重复')
    else:
        if not component_key or len([x for x in components if x.get('key')==component_key])!=1: fail('COMPONENT_SCOPE_INVALID','部件key不属于冻结对象')
        keys=[component_key]
    inputs={}; provenance=[]
    # The same frozen root feeds several exact rule mappings. Fetch original
    # detail/unit rows once in the existing GET epoch, never a preview result.
    from planning.mes_evidence_graph import raw_input,_raw
    frozen_details=raw_input(root.company_id,('frozen_workload_details',root.pk),lambda:list(
        EngineeringCalculationDetail.all_records.filter(calculation=root).select_related('uom'))) if _raw(root.company_id) is not None else None
    for binding in mapping.get('bindings',[]):
        name=binding.get('inputName')
        if name in inputs: fail('INPUT_MAPPING_INVALID','输入映射重复')
        total=Decimal(0)
        for key in keys:
            rows=[d for d in frozen_details if d.status=='succeeded' and d.rule_code==binding.get('producerCode')
                and d.rule_version==binding.get('producerVersion') and d.output_name==binding.get('sourceOutput')
                and d.uom_id==binding.get('uomId') and isinstance(d.input_snapshot,dict)
                and d.input_snapshot.get('componentKey')==key] if frozen_details is not None else list(
                    EngineeringCalculationDetail.all_records.filter(calculation=root,status='succeeded',
                        rule_code=binding.get('producerCode'),rule_version=binding.get('producerVersion'),
                        output_name=binding.get('sourceOutput'),uom_id=binding.get('uomId'),input_snapshot__componentKey=key))
            if len(rows)!=1: fail('FROZEN_SOURCE_UNKNOWN','冻结明细来源缺失或不唯一')
            detail=rows[0]
            if detail.uom.company_id!=root.company_id: fail('SOURCE_COMPANY_INVALID','来源单位越公司')
            contract=next((x for x in spec['inputs'] if x['canonicalName']==name),None)
            if contract is None or contract.get('unit')!=detail.uom.code or contract.get('unitDimension')!=detail.uom.dimension: fail('UNIT_MISMATCH','规则输入单位不匹配')
            value=Decimal(str(detail.output_value['decimal']))
            if not value.is_finite() or value<0: fail('SOURCE_VALUE_INVALID','来源数值无效')
            total+=value
            provenance.append({'detailId':detail.pk,'baselineItemId':item.pk,'componentKey':key,'sourceKind':'FROZEN_TEST_DETAIL','inputName':name,'detailSnapshot':{'ruleCode':detail.rule_code,'ruleVersion':detail.rule_version,'inputs':detail.input_snapshot,'output':detail.output_value},'baselineHash':item.content_hash})
        inputs[name]={'value':str(total),'unit':detail.uom.code,'unitDimension':detail.uom.dimension}
    if not inputs: fail('FROZEN_SOURCE_UNKNOWN','没有完整输入，禁止空成功')
    if len(inputs)!=len(mapping.get('bindings',[])) or set(inputs)!={x['canonicalName'] for x in spec['inputs']}: fail('INPUT_MAPPING_INVALID','输入映射重复或不完整')
    result=evaluate_specification(spec,inputs)
    if result['resultDomain']!='DERIVED_FACT': fail('FACT_RULE_DOMAIN_INVALID','冻结适配规则须真实声明DERIVED_FACT输出，不能伪装工序需求')
    if Decimal(result['value'])<=0: fail('POSITIVE_WORKLOAD_REQUIRED','正数需求门禁保持')
    proof={'arrangementId':arrangement.pk,'revision':arrangement.arrangement_revision,'editVersion':arrangement.edit_version,'referenceHash':arrangement.reference_hash,'rootCalculationId':root.pk,'rootResultHash':root.result_hash,'stepId':step.pk,'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(spec),'inputs':provenance,'result':result,'usagePurpose':'TEST_BUSINESS'}
    if aggregate: proof.update(scopeMode='BASELINE_ITEM_TOTAL',componentKeys=keys,assumptions=mapping.get('assumptions'),quantityAlreadyIncludesComponents=True)
    return {**proof,'readHash':digest(proof)}
