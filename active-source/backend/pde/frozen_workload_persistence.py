"""Audited test-only persistence over native calculations, facts and requirements."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction, connections
from django.utils import timezone
from .models import (EngineeringCalculationRecord as Calc, EngineeringCalculationDetail as Detail,
    EngineeringDerivedFact as Fact, EngineeringFactInput as Input, EngineeringOperationRequirement as Requirement,
    EngineeringRuleDefinition as Rule, OrderRoutingExecutionArrangement as Arrangement)
from .frozen_workload_input_service import preview
from .order_routing_execution_service import _load, fail
from .design_revision_approval_service import digest
from .engineering_rule_foundation import evaluate_specification, specification_hash
from .operation_requirement_service import _authorize, _executor, EXECUTE
from .engineering_fact_extension_service import _initialize, _finish, _audit_event
from workflow_runtime.state_transitions import create_business_object_with_initial_state as initialize
from masterdata.models import CodeRule

CONTRACT='PCE-FROZEN-TEST-WORKLOAD-V1'

def validate_input(link):
    if link.source_fact_id or not link.source_detail_id or not link.source_baseline_item_id or not link.component_key:
        raise ValidationError('冻结测试输入分支必须保存准确来源')
    root=link.source_detail.calculation; target=link.fact.calculation
    fields=('company_id','source_record_id','sales_order_item_id','engineering_instance_id')
    if root.usage_purpose!='TEST_BUSINESS' or target.usage_purpose!='TEST_BUSINESS' or target.origin_calculation_id!=root.pk or root.scope!='test_business' or root.status!='completed' or link.source_detail.status!='succeeded' or any(getattr(root,k)!=getattr(target,k) for k in fields):
        raise ValidationError('冻结测试输入用途或核算血缘不一致')
    if link.source_baseline_item.baseline_id!=root.baseline_id or link.source_detail.input_snapshot.get('componentKey')!=link.component_key:
        raise ValidationError('冻结对象或部件不一致')
    source=link.input_snapshot.get('detailSnapshot',{})
    if source!={'ruleCode':link.source_detail.rule_code,'ruleVersion':link.source_detail.rule_version,'inputs':link.source_detail.input_snapshot,'output':link.source_detail.output_value}:
        raise ValidationError('输入快照与真实冻结明细不一致')

def validate_requirement(req, *, current, user=None):
    if not req.execution_arrangement_id or not req.routing_step_id or not req.baseline_item_id or len(req.arrangement_snapshot_hash)!=64:
        raise ValidationError('测试需求必须绑定完整安排、步骤及对象')
    a=req.execution_arrangement; source=req.source_calculation; root=source.origin_calculation
    if a.usage_purpose!='TEST_BUSINESS' or req.calculation.usage_purpose!='TEST_BUSINESS' or source.usage_purpose!='TEST_BUSINESS' or not root or a.source_calculation_id!=root.pk or req.routing_step.routing_version_id!=a.routing_version_id or req.operation_id!=req.routing_step.operation_id or req.baseline_item.baseline_id!=root.baseline_id:
        raise ValidationError('测试需求安排、步骤或来源血缘不一致')
    if any(getattr(req.calculation,k)!=getattr(root,k) or getattr(source,k)!=getattr(root,k) for k in ('company_id','source_record_id','sales_order_item_id','engineering_instance_id')):
        raise ValidationError('需求上下文跨公司或外来来源')
    if current and (a.arrangement_revision!=req.arrangement_revision or a.edit_version!=req.arrangement_edit_version or Arrangement.objects.filter(predecessor=a).exists()):
        raise ValidationError('安排结果已过期')
    if req.usage_purpose!='TEST_BUSINESS' or req.source_fact.calculation_id!=source.pk or req.source_detail.calculation_id!=req.calculation_id:
        raise ValidationError('测试需求持久用途或结果来源不一致')
    rule=req.source_detail.rule; spec=rule.specification
    proof=req.trace.get('proof',{})
    if not req.component_key and proof.get('scopeMode')!='BASELINE_ITEM_TOTAL': raise ValidationError('空部件标识只允许显式冻结对象范围汇总')
    if proof.get('readHash')!=req.arrangement_snapshot_hash or proof.get('revision')!=req.arrangement_revision or proof.get('editVersion')!=req.arrangement_edit_version or proof.get('stepId')!=req.routing_step_id:
        raise ValidationError('需求安排凭据不一致')
    if req.source_detail.rule_version!=rule.version or req.source_detail.rule_code!=rule.rule_code or req.source_detail.expression_snapshot!=spec.get('expression'):
        raise ValidationError('需求规则快照不一致')
    inp=spec['inputs'][0]; result=evaluate_specification(spec,{inp['canonicalName']:{'value':req.source_fact.value['decimal'],'unit':req.source_fact.uom.code,'unitDimension':req.source_fact.uom.dimension}})
    if Decimal(result['value'])!=req.workload_quantity or req.source_detail.output_value!={'decimal':result['value']} or spec['outputs'][0].get('uomId')!=req.uom_id:
        raise ValidationError('需求结果与规则独立回算不一致')
    if current:
        if user is None: raise ValidationError('当前消费须由真实调用者重新授权')
        args={'arrangement_id':a.pk,'expected_revision':req.arrangement_revision,'expected_edit_version':req.arrangement_edit_version,'step_id':req.routing_step_id,'baseline_item_id':req.baseline_item_id,'component_key':req.component_key,'rule_id':req.source_fact.rule_id}
        if preview(user=user,**args)!=proof: raise ValidationError('来源读取凭据已失效')
    fact=req.source_fact; fact_proof=fact.trace.get('proof',{})
    if fact_proof!=proof or fact.rule_id!=proof.get('ruleId') or fact.canonical_field!=proof.get('result',{}).get('canonicalName') or fact.value!={'decimal':proof.get('result',{}).get('value')} or fact.source_detail.output_value!=fact.value:
        raise ValidationError('派生事实与真实适配规则结果不一致')
    links=list(req.source_fact.inputs.all())
    if [x.input_snapshot for x in links]!=proof.get('inputs'): raise ValidationError('冻结输入集合与来源凭据不一致')
    if not links: raise ValidationError('缺少冻结输入血缘')
    for link in links:
        validate_input(link)
        if link.source_baseline_item_id!=req.baseline_item_id or (req.component_key and link.component_key!=req.component_key): raise ValidationError('需求输入对象不一致')

def _calculation(user,root,scope,key,decision,chain,reason,origin=None):
    obj=initialize(model=Calc,initial_state='running',company_id=root.company_id,scope=scope,
        origin_calculation=origin,source_record=root.source_record,sales_order_item=root.sales_order_item,
        engineering_instance=root.engineering_instance,calculation_no=CodeRule.next_code(entity_type='production_engineering_calculation',company_id=user.company_id),
        rule_set_version=CONTRACT,idempotency_key=key,input_hash=key,started_at=timezone.now(),
        trace={'purpose':CONTRACT,'sourceSnapshot':{'sourceCalculationId':(origin or root).pk}})
    _initialize(user,obj,decision,chain,reason)
    return obj

def _detail(user,calc,rule,result,inputs,decision,chain,reason):
    output=rule.specification['outputs'][0]
    detail=initialize(model=Detail,initial_state='running',calculation=calc,sequence=1,rule=rule,
        rule_code=rule.rule_code,rule_version=rule.version,expression_snapshot=rule.specification['expression'],
        input_snapshot=inputs,output_name=result['canonicalName'],output_value={'decimal':result['value']},
        uom_id=output['uomId'],precision=rule.specification['decimalPrecision'],rounding=rule.specification['roundingMode'],started_at=timezone.now(),finished_at=timezone.now())
    _initialize(user,detail,decision,chain,reason);_finish(user,detail,'succeeded',decision,chain,reason)
    return detail

@transaction.atomic
def _generate_batch_once(*,user,rows,reason):
    if not reason or not isinstance(rows,list) or not rows: fail('BATCH_REQUIRED','必须提供非空批次及原因')
    decision=_authorize(user,EXECUTE);chain=_executor(user)
    results=[]
    for row in rows:
        if set(row)!={'source','demand_rule_id','read_hash'}: fail('FIELDS_INVALID','调用者不得指定用途、公司或数量')
        args=dict(row['source']); proof=preview(user=user,**args)
        if proof['readHash']!=row['read_hash']: fail('READ_PROOF_STALE','读取凭据已失效')
        a,bom,root,_=_load(user,args['arrangement_id'],True)
        Arrangement.objects.select_for_update().get(pk=a.pk)
        if Arrangement.objects.filter(predecessor=a).exists(): fail('ARRANGEMENT_STALE','安排已有后继修订')
        adapter=Rule.objects.get(pk=args['rule_id']); rule=Rule.objects.filter(pk=row['demand_rule_id'],company_id=user.company_id,status='released').first()
        if not rule: fail('RULE_REQUIRED','缺少已发布需求规则')
        from .operation_requirement_service import _active
        if not _active(rule): fail('RULE_NOT_EFFECTIVE','需求规则不在有效期')
        spec=rule.specification; config=spec.get('frozenTestDemand',{}); out=spec['outputs'][0]
        step=a.routing_version.steps.select_related('operation__calculation_uom').get(pk=args['step_id'])
        unit=step.operation.calculation_uom
        if unit is None or unit.company_id!=user.company_id or out.get('uomId')!=unit.pk or out.get('unit')!=unit.code or out.get('unitDimension')!=unit.dimension:
            fail('UNIT_MISMATCH','需求输出单位与固定工序不一致')
        if config!={'contractVersion':CONTRACT,'producerRuleCode':adapter.rule_code,'producerRuleVersion':adapter.version,'quantityBasis':'SOURCE_SCOPE_TOTAL'} or out.get('resultDomain')!='OPERATION_REQUIREMENT' or out.get('operationId')!=a.routing_version.steps.get(pk=args['step_id']).operation_id:
            fail('DEMAND_MAPPING_INVALID','需求规则须声明精确测试生产者与步骤工序')
        if len(spec['inputs'])!=1: fail('INPUT_MAPPING_INVALID','需求规则要求唯一明确输入')
        inp=spec['inputs'][0]
        if inp['canonicalName']!=proof['result']['canonicalName'] or inp.get('unit')!=proof['result']['unit'] or inp.get('unitDimension')!=proof['result']['unitDimension']: fail('UNIT_MISMATCH','需求输入规范名或单位不匹配')
        result=evaluate_specification(spec,{inp['canonicalName']:{'value':proof['result']['value'],'unit':inp['unit'],'unitDimension':inp['unitDimension']}})
        if Decimal(result['value'])<=0: fail('POSITIVE_WORKLOAD_REQUIRED','只保存正数需求')
        key=digest({'proof':proof,'demandRuleId':rule.pk,'demandSpec':specification_hash(spec)})
        existing=Requirement.objects.filter(generation_key=key).first()
        if existing:
            validate_requirement(existing,current=True,user=user);results.append({'id':existing.pk,'idempotent':True});continue
        ext=_calculation(user,root,'fact_extension',digest({'key':key,'type':'fact'}),decision,chain,reason,root)
        d=_detail(user,ext,adapter,proof['result'],proof,decision,chain,reason)
        fact=initialize(model=Fact,initial_state='active',calculation=ext,source_detail=d,rule=adapter,
            fact_code=proof['result']['canonicalName'],canonical_field=proof['result']['canonicalName'],sequence=1,
            value=d.output_value,uom=d.uom,source_path=f'EngineeringCalculationDetail:{d.pk}.output_value',trace={'contractVersion':CONTRACT,'resultDomain':'DERIVED_FACT','proof':proof})
        _initialize(user,fact,decision,chain,reason)
        for i,source in enumerate(proof['inputs'],1):
            Input(fact=fact,source_kind='FROZEN_TEST_DETAIL',source_detail_id=source['detailId'],source_baseline_item_id=source['baselineItemId'],component_key=source['componentKey'],input_name=source['inputName'],sequence=i,source_hash=digest(source),input_snapshot=source).save()
        ext.result_hash=digest(proof['result']);ext.finished_at=timezone.now();ext.save();_finish(user,ext,'completed',decision,chain,reason)
        calc=_calculation(user,root,'operation_requirement',key,decision,chain,reason)
        detail=_detail(user,calc,rule,result,{'sourceFactId':fact.pk,'sourceHash':digest(proof)},decision,chain,reason)
        calc.result_hash=digest(result);calc.finished_at=timezone.now();calc.save();audit=_finish(user,calc,'completed',decision,chain,reason)
        req=Requirement(calculation=calc,source_detail=detail,sequence=1,operation_id=out['operationId'],
            workload_quantity=Decimal(result['value']),uom_id=out['uomId'],source_path=f'EngineeringCalculationDetail:{detail.pk}.output_value',
            quantity_basis='SOURCE_SCOPE_TOTAL',basis_quantity=root.sales_order_item.quantity,basis_uom=root.sales_order_item.uom,
            source_calculation=ext,source_fact=fact,generation_key=key,source_hash=digest(proof),input_hash=digest(spec),created_by=user,audit_record=audit,
            usage_purpose='TEST_BUSINESS',execution_arrangement=a,arrangement_revision=a.arrangement_revision,arrangement_edit_version=a.edit_version,
            arrangement_snapshot_hash=proof['readHash'],routing_step_id=args['step_id'],baseline_item_id=args['baseline_item_id'],component_key=args['component_key'],
            trace={'contractVersion':CONTRACT,'ruleId':rule.pk,'ruleVersion':rule.version,'proof':proof})
        req.save();results.append({'id':req.pk,'idempotent':False})
    return results


def generate_batch(*, user, rows, reason):
    """Retry a fully rolled-back SQLite contention; never treat lock errors as success."""
    from django.db import OperationalError
    import time
    for attempt in range(8):
        try:
            return _generate_batch_once(user=user, rows=rows, reason=reason)
        except OperationalError as error:
            connection=connections['default']
            if connection.vendor!='sqlite' or connection.in_atomic_block or not any(x in str(error).lower() for x in ('locked','busy')) or attempt==7:
                raise
            connection.close()
            time.sleep(0.05 * (attempt+1))


def read_saved_workloads(*,user,arrangement):
    """One server projection shared by arrangement API, UI and diagnostics."""
    from .models import EngineeringOperationRequirement
    rows=[]
    from django.db.models import Prefetch
    inputs=Input.objects.select_related('source_detail').prefetch_related(
        'source_detail__calculation','source_baseline_item','fact__calculation')
    requirements=EngineeringOperationRequirement.objects.filter(execution_arrangement=arrangement).select_related(
        'operation','uom','source_detail__rule','source_calculation','source_fact','baseline_item','routing_step','calculation'
        ).prefetch_related('execution_arrangement','source_calculation__origin_calculation',
            'source_fact__uom','source_fact__source_detail','source_fact__rule',
            Prefetch('source_fact__inputs',queryset=inputs)).order_by('routing_step__sequence','pk')
    for req in requirements:
        current=True; reason='已生成测试作业量；禁止正式生产承接'
        try:validate_requirement(req,current=True,user=user)
        except Exception as error:
            current=False;reason='历史结果／需重新核定：'+str(error)
        links=list(req.source_fact.inputs.all())
        component_names={x.get('key'):x.get('name') for x in req.baseline_item.content_snapshot.get('revision',{}).get('designData',{}).get('calculationInputs',{}).get('components',[])}
        rows.append({'id':req.pk,'stepId':req.routing_step_id,'sequence':req.routing_step.sequence,'operationName':req.operation.name,
            'quantityText':format(req.workload_quantity,'.6f'),'unitLabel':req.uom.name,'purposeLabel':'测试用途（不得制造）',
            'statusLabel':reason,'current':current,'arrangementRevision':req.arrangement_revision,'editVersion':req.arrangement_edit_version,
            'baselineItemId':req.baseline_item_id,'componentKeys':[x.component_key for x in links],
            'sourceLabel':req.source_fact.rule.specification.get('sourceEvidence',{}).get('assumption') or req.source_fact.rule.rule_name,'ruleVersion':req.source_detail.rule_version,
            'assumptions':req.trace.get('proof',{}).get('assumptions'),
            'inputs':[{'detailId':x.source_detail_id,'componentKey':x.component_key,'componentLabel':component_names.get(x.component_key) or '冻结部件','fieldLabel':x.source_detail.output_name,
                'quantityText':x.source_detail.output_value['decimal'],'producerLabel':x.source_detail.rule_code+'/'+x.source_detail.rule_version} for x in links]})
    required=set(arrangement.decisions.filter(decision='REQUIRED').values_list('routing_step_id',flat=True))
    ready=bool(required) and not arrangement.decisions.filter(decision='PENDING').exists() and required<={x['stepId'] for x in rows if x['current']}
    return {'rows':rows,'currentCount':sum(x['current'] for x in rows),'workloadReady':ready,'overallStatusLabel':'本安排应执行步骤的测试作业量已全部保存；用途隔离、产能和日历仍须分别核验' if ready else '部分步骤已生成测试作业量；其他步骤未完成，作业量环节尚未就绪','formalManufacturingEligible':False}
