"""General TEST_BUSINESS material handoff on existing rule/requirement ledgers."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from system.models import OrganizationOperatingAuditRecord
from .models import EngineeringCalculationRecord,EngineeringCalculationDetail,EngineeringRuleDefinition,EngineeringMaterialRequirement
from .engineering_calculation_service import EngineeringCalculationService,EngineeringCalculationError
from .design_revision_approval_service import digest

def fail(code,message):raise EngineeringCalculationError(code,message)

def authorize(user, action, company):
    if user.company_id != company:fail('SCOPE_DENIED','不可跨公司承接测试核算。')
    return EngineeringCalculationService._authorize(user=user,action_code=action,company_id=company)

def validate_source(record,user=None):
    if record.scope!='test_business' or record.status!='completed':fail('TEST_COMPLETED_CALCULATION_REQUIRED','仅接受已完成的测试业务核算。')
    from .test_calculation_persistence import consume_test
    from system.models import User
    actor=user or User.objects.get(pk=record.trace['savedBy']['id'])
    try:return consume_test(actor,record.pk)
    except Exception as e:
        if isinstance(e,EngineeringCalculationError):raise
        fail(getattr(e,'code','TEST_SOURCE_INVALID'),getattr(e,'message',str(e)))

def validate_requirements(record,requirements):
    frozen=validate_source(record)['snapshot']
    expected={x['original']['key'] for x in frozen['inputs']}
    covered=set()
    for req in requirements:
        proof=req.trace.get('testBusiness') or {}
        rule=EngineeringRuleDefinition.objects.filter(pk=proof.get('ruleId'),company_id=record.company_id,status='released').first()
        detail=req.source_detail
        key=detail.input_snapshot.get('componentKey')
        if not rule or digest(rule.specification)!=proof.get('ruleHash'):fail('TEST_MAPPING_CHANGED','测试材料映射已变化或失效，请重新核定。')
        contract=rule.specification.get('testBusinessContract') or {}
        if rule.specification.get('contractCode')!='PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING-V1' or contract.get('purposeContract')!='PCE-TEST-BUSINESS-MATERIAL-MAPPING-V1':
            fail('TEST_MAPPING_CONTRACT_INVALID','测试映射必须复用受治理材料映射契约。')
        from workflow_runtime.models import BusinessStateTransition
        transitions=list(BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition',object_id=rule.pk).order_by('pk'))
        if [(x.source_state,x.target_state) for x in transitions] != [('', 'draft'),('draft','reviewed'),('reviewed','released')]:
            fail('TEST_MAPPING_STATE_FACT_REQUIRED','测试映射缺少统一初始化、审核或发布转换事实。')
        for state in transitions:
            reference=state.audit_reference.split(':')
            if len(reference)!=2 or reference[0]!='OrganizationOperatingAuditRecord' or not OrganizationOperatingAuditRecord.objects.filter(pk=reference[1],target_type='EngineeringRuleDefinition',target_id=rule.pk,actor_id=state.operator_id,organization_id=record.company_id).exists():
                fail('TEST_MAPPING_AUDIT_REQUIRED','测试映射状态转换缺少对应权威审计。')
        checks=(contract.get('calculationId')==record.pk,contract.get('resultHash')==record.result_hash,
                contract.get('componentKey')==key,contract.get('detailId')==detail.pk,
                contract.get('materialId')==req.material_id,contract.get('uomId')==req.uom_id,
                detail.calculation_id==record.pk,req.calculation_id==record.pk,
                key in expected,req.material.company_id==record.company_id,
                req.material.base_uom_id==req.uom_id,req.quantity_basis=='ORDER_TOTAL',
                str(req.net_quantity)==str(Decimal(contract.get('quantity','-1'))),
                req.net_quantity==Decimal(str(detail.output_value.get('decimal'))),
                req.order_quantity==1,req.item_role=='material',req.requirement_type=='manufacturing',req.supply_type=='BUY',
                req.scrap_rate_status=='not_maintained',req.scrap_rate is None,req.gross_quantity is None,
                req.order_specification==contract.get('orderSpecification'),proof.get('resultHash')==record.result_hash)
        if not all(checks):fail('TEST_REQUIREMENT_SOURCE_MISMATCH','测试材料需求与冻结明细、材料、单位或规则不一致。')
        covered.add(key)
    complete=expected==covered and bool(expected)
    blocker=None if complete else {'code':'TEST_MATERIAL_REQUIREMENT_REQUIRED','statusLabel':'缺少测试材料需求映射','message':'冻结部件尚未全部形成有材料、规格、单位和用量依据的需求；不能生成空BOM。'}
    return {'complete':complete,'firstRealBlocker':blocker,'targetDesignItemCount':len(expected),'coveredDesignItemCount':len(covered),'missingComponentKeys':sorted(expected-covered),'purposeLabel':'测试业务：仅限草稿，禁止正式评审、发布及制造'}

@transaction.atomic
def apply_mapping(*,user,calculation_id,component_key,material_id,rule_code,version,reason,idempotency_key):
    """Explicit development mapping; no material/name guessing or calculation rerun."""
    record=EngineeringCalculationRecord.all_records.select_for_update().get(pk=calculation_id)
    for action in ('production.engineering.calculation.view','production.engineering.rule.maintain','production.engineering.rule.release','production.engineering.calculation.execute','production.master_data.bom.maintain'):
        authorize(user,action,record.company_id)
    frozen=validate_source(record,user)['snapshot']
    rows=[r for r in frozen['rows'] if r.get('componentKey')==component_key and r.get('column')=='S']
    if len(rows)!=1:fail('TEST_COMPONENT_AREA_REQUIRED','测试映射须明确绑定一个已保存的工程净面积明细。')
    details=list(EngineeringCalculationDetail.all_records.filter(calculation=record,input_snapshot__componentKey=component_key).order_by('sequence'))
    detail=next((d for d in details if d.sequence==frozen['rows'].index(rows[0])+1),None)
    if not detail:fail('TEST_DETAIL_REQUIRED','缺少精确冻结计算明细。')
    from masterdata.models import Material
    material=Material.objects.select_related('base_uom').get(pk=material_id,company_id=record.company_id)
    if not material.is_active or material.base_uom.code!='m2':fail('TEST_MATERIAL_UOM_INVALID','此受控净面积映射要求有效平方米基本单位物料。')
    quantity=Decimal(str(detail.output_value['decimal']))
    if quantity<=0:fail('TEST_POSITIVE_REQUIREMENT_REQUIRED','材料需求必须为正，不能以默认数量补齐。')
    spec_order={'structureRole':component_key,'materialSpecification':material.specification,'businessPurpose':'TEST_BUSINESS','validationOnly':True}
    contract={'purposeContract':'PCE-TEST-BUSINESS-MATERIAL-MAPPING-V1','calculationId':record.pk,'resultHash':record.result_hash,'componentKey':component_key,'detailId':detail.pk,'materialId':material.pk,'uomId':material.base_uom_id,'quantity':str(quantity),'orderSpecification':spec_order,'authority':reason}
    spec={'sourceEvidence':{'reference':reason,'sourceDetailId':detail.pk,'calculationId':record.pk,'calculationResultHash':record.result_hash},'rulePackage':{'code':'PCE-TEST-BUSINESS-MATERIAL-MAPPING','version':'V1'},'contractCode':'PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING-V1','testBusinessContract':contract,
          'inputs':[{'canonicalName':'source_fact_value','valueType':'decimal','unit':'m2','unitDimension':'area','sourceType':'ENGINEERING_DERIVED','required':True,'unitRequired':True}],
          'outputs':[{'canonicalName':'test_material_quantity','valueType':'decimal','unit':'m2','unitDimension':'area','resultDomain':'MATERIAL_REQUIREMENT','materialId':material.pk,'outputUom':'m2','quantityBasis':'ORDER_TOTAL','quantityExpression':'source_fact_value','sourceDetailId':detail.pk}],
          'expression':'source_fact_value','dependencies':[],'decimalPrecision':18,'outputScale':6,'roundingMode':'ROUND_HALF_UP','priority':100,
          'applicability':{'orderNo':record.sales_order_item.sales_order.order_no,'salesOrderItemId':record.sales_order_item_id,'designItemNo':record.design_revision.design_item.item_no,'calculationId':record.pk,'componentKey':component_key,'businessPurpose':'TEST_BUSINESS'}}
    from .production_foundation_service import ProductionFoundationService,EngineeringLifecycleService
    existing=EngineeringRuleDefinition.objects.filter(company_id=record.company_id,rule_code=rule_code,version=version).first()
    if existing and existing.specification!=spec:fail('TEST_MAPPING_CONFLICT','同版本映射内容冲突，不覆盖旧映射。')
    if not existing:
        result=ProductionFoundationService.write('engineering-rule-definitions',user=user,payload={'company_id':record.company_id,'rule_code':rule_code,'rule_name':'隔离验证材料净面积映射','version':version,'rule_kind':'mapping','specification':spec,'status':'draft','reason':reason},idempotency_key=idempotency_key+':rule',source_identity={'sourceSystem':'PCE_TEST_BUSINESS','sourceType':'EXPLICIT_TEST_MAPPING','externalId':rule_code+':'+version,'sourceObjectType':'EngineeringMaterialMapping','source_version':version})
        existing=EngineeringRuleDefinition.objects.get(pk=result['row']['id'])
        for state in ('reviewed','released'):
            EngineeringLifecycleService.transition('engineering-rule-definitions',object_id=existing.pk,target_status=state,user=user,reason=reason)
        existing.refresh_from_db()
    req=EngineeringMaterialRequirement.objects.filter(source_detail=detail).first()
    if req:
        validate_requirements(record,list(record.material_requirements.select_related('material','uom','source_detail')))
        return {'id':req.pk,'idempotent':True}
    from .product_design_service import _write_request,_commit_request
    request,created,_=_write_request(user=user,action_code='production.engineering.material_requirement.create',entity_type='EngineeringMaterialRequirement',key=idempotency_key,request_body=contract)
    req=EngineeringMaterialRequirement(calculation=record,source_detail=detail,sequence=detail.sequence,material=material,uom=material.base_uom,quantity_basis='ORDER_TOTAL',calculated_quantity=quantity,order_quantity=1,net_quantity=quantity,item_role='material',requirement_type='manufacturing',supply_type='BUY',order_specification=spec_order,scrap_rate_status='not_maintained',source_path=f'testCalculation.details[{detail.pk}]',trace={'testBusiness':{'ruleId':existing.pk,'ruleHash':digest(existing.specification),'resultHash':record.result_hash,'componentKey':component_key},'authority':reason})
    req.full_clean();req.save()
    audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=record.company_id,action_code='production.engineering.material_requirement.create',target_type='EngineeringMaterialRequirement',target_id=req.pk,target_label=record.calculation_no,reason=reason,after_snapshot={'requirementId':req.pk,'ruleId':existing.pk,'usagePurpose':'TEST_BUSINESS','sourceCalculationId':record.pk})
    _commit_request(request,{'requirementId':req.pk,'auditId':audit.pk})
    return {'id':req.pk,'idempotent':False}




