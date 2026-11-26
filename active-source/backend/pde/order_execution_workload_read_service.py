"""Read-only order-arrangement admission into the existing workload authority.

This reader does not evaluate expressions, create derived facts or requirements,
allocate capacity, or treat a saved net area as an operation quantity.
"""
from copy import deepcopy
from django.db import transaction
from .production_foundation_service import ProductionFoundationError, _snapshot
from .design_revision_approval_service import digest
from . import operation_workload_source_service as sources
from . import operation_requirement_service as native
from . import order_routing_execution_service as arrangements
from .models import (OrderRoutingExecutionArrangement, CapacityProductType, EngineeringRuleDefinition,
    EngineeringCalculationDetail, EngineeringDerivedFact, EngineeringOperationRequirement, StandardCapacity)
from system.models import Process
from masterdata.models import UnitOfMeasure

CONTRACT='PCE-ORDER-EXECUTION-WORKLOAD-READ-V1'

def fail(code,message,**details):
    raise ProductionFoundationError(code,message,details)

def _scoped_projection(operation, projection, kind, context, rules, rule_types, selection_cache):
    value=deepcopy(projection)
    if kind is None:
        value.update(sources=[],blockers=[{'code':'PRODUCT_TYPE_UNRESOLVED','statusLabel':'当前分类及工艺不能唯一定位有效产能产品类型'}])
        return sources._finish_projection(value)
    value['sources']=[s for s in value['sources'] if s['productTypeId']==kind.pk]
    value['blockers']=[b for b in value['blockers'] if b.get('code')!='WORKLOAD_SOURCE_RULE_AMBIGUOUS'
        and (not b.get('ruleId') or rule_types.get(b['ruleId'])==kind.pk)]
    value=sources.restrict_operation_projection(value,context)
    if operation.pk not in selection_cache:
        _,entries=sources._selection_entries(operation)
        selection_cache[operation.pk]=None
        if entries:
            options=sources.source_scheme_options(operation,rules=rules,projection=projection)
            selection_cache[operation.pk]=sources.source_selection_readback(operation,options=options)
    selection=selection_cache[operation.pk]
    if selection:
        chosen=sources._scheme_for_scope(selection['selections'],sources._scheme_scope(operation,kind.pk,context))
        if chosen:
            selected_ids={row['ruleId'] for row in chosen['ruleRefs']}
            value['unselectedSources']=[s for s in value['sources'] if s['ruleId'] not in selected_ids]
            value['sources']=[s for s in value['sources'] if s['ruleId'] in selected_ids]
            value=sources._finish_projection(value)
        value['sourceSelection']=deepcopy(selection)
    return value

@transaction.atomic
def read_arrangement_workload(*,user,arrangement_id,baseline_item_id=None,
                              expected_edit_version=None,expected_read_hash=None):
    native._authorize(user,native.VIEW)
    native._authorize(user,sources.RULE_VIEW)
    sources._id(arrangement_id,'订单安排ID')
    if baseline_item_id is not None:sources._id(baseline_item_id,'冻结对象ID')
    # One source/version/authorization proof for all steps, owned by this read.
    arrangement=arrangements.read(user=user,arrangement_id=arrangement_id,baseline_item_id=baseline_item_id)
    if expected_edit_version is not None and (type(expected_edit_version) is not int or expected_edit_version!=arrangement['editVersion']):
        fail('ORDER_WORKLOAD_ARRANGEMENT_CHANGED','订单执行安排编辑序号已变化，须重新核定作业量来源',currentEditVersion=arrangement['editVersion'])
    obj=OrderRoutingExecutionArrangement.objects.select_related('source_calculation__sales_order_item__uom',
        'engineering_instance','routing_version__routing').get(pk=arrangement_id,company_id=user.company_id)
    record=obj.source_calculation;instance=obj.engineering_instance;item=record.sales_order_item
    kinds=[row for row in CapacityProductType.objects.filter(company_id=obj.company_id,
        product_category_id=instance.product_category_id,manufacturing_process_type_id=instance.selected_process_type_id)
        if native._active(row)]
    kind=kinds[0] if len(kinds)==1 else None
    operations={op.pk:op for op in Process.objects.filter(company_id=obj.company_id,
        pk__in={row['operationId'] for row in arrangement['steps']}).select_related('calculation_uom','work_center','workshop')}
    # Use the existing rule metadata validator once, then its native exact-scope
    # and saved-choice helpers. No second formula/quantity engine is introduced.
    projections=sources.project_operation_sources(operations.values(),obj.company_id,_apply_selection=False)
    rules=sources._rules(obj.company_id);rule_types={rule.pk:(rule.specification.get('outputs') or [{}])[0].get('productTypeId')
        for rule in rules if isinstance(rule.specification,dict) and isinstance(rule.specification.get('outputs'),list) and rule.specification['outputs']}
    raw_by_operation={}
    for rule in rules:
        spec=rule.specification if isinstance(rule.specification,dict) else {};outputs=spec.get('outputs')
        if kind and isinstance(outputs,list) and len(outputs)==1 and isinstance(outputs[0],dict):
            output=outputs[0]
            if output.get('resultDomain')=='OPERATION_REQUIREMENT' and output.get('productTypeId')==kind.pk:
                raw_by_operation.setdefault(output.get('operationId'),[]).append(_snapshot(rule))
    details=list(EngineeringCalculationDetail.all_records.filter(calculation_id=record.pk).order_by('sequence'))
    facts=list(EngineeringDerivedFact.objects.filter(calculation_id=record.pk).select_related('uom').order_by('sequence','pk'))
    requirements=list(EngineeringOperationRequirement.objects.filter(source_calculation_id=record.pk).order_by('pk'))
    capacities=list(StandardCapacity.objects.filter(company_id=obj.company_id,product_type=kind,
        operation_id__in=operations).select_related('uom','work_center')) if kind else []
    from .daily_capacity_service import capacity_source_rules
    capacity_proof=capacity_source_rules(kind,company_id=obj.company_id,on_date=native._today()) if kind else {'status':'UNRESOLVED','manifest':{}}
    scope={'companyId':obj.company_id,'orderId':item.sales_order_id,'salesOrderItemId':item.pk,
        'engineeringInstanceId':instance.pk,'calculationId':record.pk,'BOMVersionId':obj.bom_version_id,
        'baselineId':obj.reference_proof['baselineId'],'baselineItemId':baseline_item_id,
        'arrangementId':obj.pk,'arrangementRevision':obj.arrangement_revision,'arrangementEditVersion':obj.edit_version,
        'routingId':obj.routing_version.routing_id,'routingVersionId':obj.routing_version_id,'usagePurpose':obj.usage_purpose}
    units={u.pk:u for u in UnitOfMeasure.objects.filter(company_id=obj.company_id,
        pk__in={d.uom_id for d in details}|{op.calculation_uom_id for op in operations.values()})}
    saved_details=[{'detailId':d.pk,'componentKey':(d.input_snapshot or {}).get('componentKey'),
        'name':d.output_name,'value':deepcopy(d.output_value),'uomId':d.uom_id,
        'unitLabel':units[d.uom_id].name if d.uom_id in units else '单位待核定',
        'ruleId':d.rule_id,'ruleCodeSnapshot':d.rule_code,'ruleVersionSnapshot':d.rule_version,
        'statusLabel':d.get_status_display(),'sourceTypeLabel':'已保存测试工程明细（不是原生派生事实，也不是工序作业量）'} for d in details]
    saved_workloads=arrangement.get('operationWorkloads',{})
    saved_by_step={x['stepId']:x for x in saved_workloads.get('rows',[]) if x['current'] and (baseline_item_id is None or x['baselineItemId']==baseline_item_id)}
    rows=[];selection_cache={}
    for step in arrangement['steps']:
        operation=operations[step['operationId']]
        context={'routingId':obj.routing_version.routing_id,'routingVersionId':obj.routing_version_id,'routingStepId':step['stepId']}
        projected=_scoped_projection(operation,projections[operation.pk],kind,context,rules,rule_types,selection_cache)
        candidates=projected['sources'];blockers=deepcopy(projected['blockers'])
        if not candidates:blockers.append({'code':'ORDER_OPERATION_RULE_REQUIRED','statusLabel':'当前产品类型及固定步骤缺少有效作业量规则；旧驱动文字不等于规则'})
        if not facts:blockers.append({'code':'ORDER_NATIVE_SOURCE_FACT_REQUIRED','statusLabel':'本核算没有可供工序规则引用的原生派生事实；不能把净面积明细改名代用'})
        if obj.usage_purpose=='TEST_BUSINESS':blockers.append({'code':'TEST_FROZEN_MAPPING_REVIEW_REQUIRED','statusLabel':'测试用途须经独立冻结字段映射及规则血缘核验；现有候选未获业务映射核定，不生成需求'})
        relevant=[]
        selectors={s['sourceCanonicalField'] for s in candidates}
        for fact in facts:
            if fact.canonical_field not in selectors:continue
            trace=fact.trace if isinstance(fact.trace,dict) else {}
            if baseline_item_id is not None and trace.get('baselineItemId')!=baseline_item_id:continue
            relevant.append({'factId':fact.pk,'canonicalField':fact.canonical_field,'value':deepcopy(fact.value),
                'uomId':fact.uom_id,'sourceDetailId':fact.source_detail_id,
                'statusLabel':'原生事实候选值（仍须原规则血缘及口径校验，不作为本安排已保存作业量）'})
        current_caps=[cap for cap in capacities if cap.operation_id==operation.pk and cap.work_center_id==step['workCenterId'] and native._active(cap)]
        cap_facts=[{'id':cap.pk,'code':cap.code,'quantity':str(cap.quantity),'uomId':cap.uom_id,'unitLabel':cap.uom.name,
            'timeBasis':cap.time_basis,'timeBasisQuantity':str(cap.time_basis_quantity),'timeUnit':cap.time_unit,
            'measurementStatus':cap.measurement_status,'measurementLabel':'模拟测试正数产能（非实测）' if cap.conditions.get('measurementEvidenceType')=='SIMULATED_TEST' else cap.get_measurement_status_display(),
            'sourceCell':(cap.conditions or {}).get('sourceCell'),'sourceHash':(cap.conditions or {}).get('sourceSha256'),
            'scopeLabel':'当前产品类型／工序／工作中心的标准产能，独立于订单作业量'} for cap in current_caps]
        if not current_caps:
            historical_not_applicable=operation.pk in capacity_proof.get('manifest',{}).get('nonApplicableOperationIds',[])
            blockers.append({'code':'ORDER_STANDARD_CAPACITY_UNAVAILABLE','statusLabel':
                '该类型产能矩阵历史为空白；与当前安排独立核定，不据空白把本单改为不执行' if historical_not_applicable else '当前准确范围无有效标准产能记录，不由作业量推补'})
        # This is a source-admission read. An unbound legacy EOR or a source
        # number cannot become an arrangement-revision workload by assertion.
        if step['decision']=='PENDING':label='执行待核定；作业量未知';blockers.insert(0,{'code':'ORDER_EXECUTION_PENDING','statusLabel':'保留待核定，不静默跳过或改为不执行'})
        elif step['decision']=='NOT_APPLICABLE':label='依据已保存安排本单不执行；不以0填充作业量'
        else:label='本单执行，但工序作业量尚无完整依据'
        saved=saved_by_step.get(step['stepId'])
        if saved: blockers=[x for x in blockers if x['code'] not in ('ORDER_OPERATION_RULE_REQUIRED','ORDER_NATIVE_SOURCE_FACT_REQUIRED','TEST_FROZEN_MAPPING_REVIEW_REQUIRED')]
        rows.append({**step,'scope':{**scope,'routingStepId':step['stepId'],'operationId':operation.pk},
            'applicableObjects':deepcopy(arrangement['objects']),'legacyDriverLabel':operation.quantity_driver or '旧驱动文字未维护',
            'ruleProjection':projected,'sourceCandidates':relevant,'rawScopedRules':raw_by_operation.get(operation.pk,[]),
            'workloadQuantity':saved['quantityText'] if saved else None,'savedWorkload':saved,'workloadStatusLabel':saved['statusLabel'] if saved else label,'workloadUnitId':operation.calculation_uom_id,
            'workloadUnitLabel':operation.calculation_uom.name if operation.calculation_uom_id else '单位待核定',
            'quantityBasisLabel':'本轮受治理测试处理范围总量，已含部件数量；每个固定步骤仅一次' if saved else '按选定规则的固定来源范围总量办理，不再次乘订单数量' if candidates and all(s['quantityBasis']=='SOURCE_SCOPE_TOTAL' for s in candidates) else '尚无适用规则，数量口径待核定',
            'sourceOrderQuantity':str(item.quantity),'sourceOrderUomId':item.uom_id,
            'standardCapacity':cap_facts,'capacitySourceStatus':capacity_proof.get('status'),
            'capacityCheckStatusLabel':'作业量已保存；标准产能、日历与占用仍须独立核验，未生成日期排产' if saved else '未核算产能占用：缺少本工序可信作业量；0产能配套语义不等于0作业量',
            'capacityOccupancy':None,'duration':None,'blockers':blockers,
            'responsibilityLabel':'软件负责人：保护用途／安排修订及来源；工程规则维护负责人：维护各测试处理范围与计量依据；工艺负责人：执行条件及实际驱动；产能负责人：标准范围冲突',
            'persistedArrangementWorkload':bool(saved),'formalManufacturingEligible':False})
    proof={'scope':scope,'referenceHash':obj.reference_hash,'calculationInputHash':record.input_hash,
        'calculationResultHash':record.result_hash,'arrangement':_snapshot(obj),
        'decisions':[_snapshot(x) for x in obj.decisions.order_by('pk')],
        'productType':_snapshot(kind) if kind else None,'operations':[_snapshot(op) for op in operations.values()],
        'details':[_snapshot(d) for d in details],'facts':[_snapshot(f) for f in facts],
        'rules':[_snapshot(rule) for rule in rules],'capacities':[_snapshot(cap) for cap in capacities],
        'units':[_snapshot(u) for u in units.values()],'date':native._today().isoformat()}
    read_hash=digest(proof)
    if expected_read_hash is not None and expected_read_hash!=read_hash:
        fail('ORDER_WORKLOAD_SOURCE_CHANGED','安排、规则或来源已变化，旧核定不能继续使用，须重新读取',currentReadHash=read_hash)
    return {'contractVersion':CONTRACT,'factSource':'server','scope':scope,'readHash':read_hash,
        'arrangementStatusLabel':arrangement['statusLabel'],'purposeLabel':arrangement['purposeLabel'],
        'sourceIdentity':{k:arrangement[k] for k in ('orderNo','bomVersionName','sourceCalculationNo','sourceId','routingCode','routingName','routingVersionName','routingVersionRevision')},
        'productType':{'id':kind.pk,'code':kind.code,'name':kind.name} if kind else None,
        'productTypeBasisLabel':'从订单实例当前分类及工艺匹配；不表示颜色、色样或日常方案已获确认',
        'savedEngineeringDetails':saved_details,'nativeDerivedFactCount':len(facts),'existingNativeRequirementCount':len(requirements),
        'existingNativeRequirementsLabel':'历史需求未绑定本安排修订，不能冒认为本安排已承接的作业量',
        'steps':rows,'stepCount':len(rows),'workloadReady':saved_workloads.get('workloadReady',False),'savedWorkloadCount':len(saved_by_step),'formalManufacturingEligible':False,
        'readinessStatusLabel':'应执行步骤测试作业量已保存；正式用途、标准产能及日历准入独立核验' if saved_workloads.get('workloadReady') else '只读核定已加载；实际工序作业量仍受来源及规则映射缺项阻断',
        'nativeProductionContractPreserved':True,'generated':False,'databaseBusinessWriteCount':0,'auditWriteCount':0,
        'diagnostics':{'arrangementReadCalls':1,'metadataBatchCalls':1,'quantityRuleEvaluations':0,'persistentCacheUsed':False},
        'requestIdentity':{'userId':user.pk,'username':user.username,'companyId':user.company_id}}
