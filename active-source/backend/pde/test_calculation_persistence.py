"""TEST_BUSINESS persistence in the existing engineering calculation tables."""
import hashlib
from pathlib import Path
from time import sleep
from django.db import transaction,OperationalError,IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from masterdata.models import CodeRule,UnitOfMeasure
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.state_transitions import create_business_object_with_initial_state,transition_business_object
from .models import EngineeringCalculationRecord,EngineeringCalculationDetail
from .product_design_service import ProductDesignError,_write_request,_commit_request
from .engineering_calculation_service import EngineeringCalculationService,EngineeringCalculationError
from .design_revision_approval_service import digest
from .test_calculation_preview import preview,baseline_for,context_for,FIELDS
ACTION='production.engineering.calculation.execute'

def validate_record_binding(record):
    if record.approval_scope!='TEST_BUSINESS' or not all((record.company_id,record.baseline_id,record.design_revision_id,record.design_approval_id,record.sales_order_item_id,record.engineering_instance_id,record.source_record_id)):
        raise ValidationError('测试核算必须精确绑定测试用途及完整来源。')
    b,r,a=record.baseline,record.design_revision,record.design_approval
    if (b.company_id!=record.company_id or b.sales_order_id!=record.sales_order_item.sales_order_id or b.approval_scope!='TEST_BUSINESS'
        or record.engineering_instance.sales_order_item_id!=record.sales_order_item_id
        or record.engineering_instance.source_record_id!=record.source_record_id
        or record.engineering_instance.company_id!=record.company_id or record.source_record.company_id!=record.company_id
        or r.design_item.sales_order_item_id!=record.sales_order_item_id or r.approval_id!=a.pk
        or a.company_id!=record.company_id or a.engineering_instance_id!=record.engineering_instance_id
        or record.supersedes_id or record.origin_calculation_id
        or not b.items.filter(design_revision=r,source_record_id=record.source_record_id).exists()):
        raise ValidationError('测试核算与公司、订单行、实例、基线或精确批准关联不一致。')

def rule_snapshot(company):
    from .formal_engineering_continuation_service import _package_rules,formal_rule_blueprints
    from .calculation_batch_reuse import VERSION
    rules=_package_rules(company,None)
    blueprints={b['rule_code']:b['specification'] for b in formal_rule_blueprints()}
    if any(digest(r.specification)!=digest(blueprints[code]) for code,r in rules.items()):
        raise ProductDesignError('TEST_RULE_CONTRACT_CHANGED','当前规则定义与原Decimal适配契约不一致，不保存或继续消费。',409)
    files=('cabinet_calculation_adapter.py','native_design_calculation_adapter.py','calculation_batch_reuse.py','engineering_rule_foundation.py','engineering_condition_options.py')
    return {'adapterVersion':VERSION,'definitions':[{'id':r.pk,'code':r.rule_code,'version':r.version,'hash':digest(r.specification)} for r in rules.values()],
            'implementationHashes':{f:hashlib.sha256((Path(__file__).parent/f).read_bytes()).hexdigest() for f in files}},rules['APPROVED_SOURCE_NET']

def authorize(user,write=False):
    return EngineeringCalculationService._authorize(user=user,action_code=ACTION if write else 'production.engineering.calculation.view',company_id=user.company_id)

from planning.verified_read_memo import verified_source_read
@verified_source_read
def read_record(user,record_id):
    authorize(user)
    obj=EngineeringCalculationRecord.all_records.filter(pk=record_id,company_id=user.company_id,scope='test_business').first()
    if not obj:raise ProductDesignError('TEST_CALCULATION_NOT_FOUND','测试核算记录不存在或不可查看。',404)
    t=obj.trace; frozen=t.get('resultSnapshot') or {}
    details=list(EngineeringCalculationDetail.all_records.filter(calculation=obj).order_by('sequence'))
    context=t.get('context') or {}
    audit=OrganizationOperatingAuditRecord.objects.filter(target_type='EngineeringCalculationRecord',target_id=obj.pk,action_code=ACTION,organization_id=obj.company_id).order_by('pk').first()
    bound={'companyId':obj.company_id,'salesOrderId':obj.sales_order_item.sales_order_id,'salesOrderItemId':obj.sales_order_item_id,
           'orderEngineeringInstanceId':obj.engineering_instance_id,'baselineId':obj.baseline_id,'designRevisionId':obj.design_revision_id,
           'sourceRecordId':obj.source_record_id,'approvalId':obj.design_approval_id}
    detail_snapshot=[{'sequence':d.sequence,'ruleId':d.rule_id,'ruleCode':d.rule_code,'ruleVersion':d.rule_version,'expression':d.expression_snapshot,'inputs':d.input_snapshot,'output':d.output_value,'name':d.output_name,'uomId':d.uom_id,'precision':d.precision,'rounding':d.rounding} for d in details]
    if (digest(frozen)!=obj.result_hash or digest(t.get('inputSnapshot'))!=obj.input_hash
        or digest(t.get('ruleSnapshot'))!=obj.rule_graph_hash or digest(detail_snapshot)!=t.get('detailHash')
        or any(context.get(k)!=v for k,v in bound.items()) or context!=(t.get('inputSnapshot') or {}).get('context')
        or context!=frozen.get('context') or obj.rule_set_version!=(t.get('ruleSnapshot') or {}).get('adapterVersion')):
        raise ProductDesignError('TEST_CALCULATION_SNAPSHOT_INVALID','已保存测试核算证据或明细哈希不一致。',409)
    from workflow_runtime.models import BusinessStateTransition
    if (not audit or audit.actor_id!=(t.get('savedBy') or {}).get('id') or audit.reason!=t.get('reason')
        or audit.after_snapshot.get('inputHash')!=obj.input_hash or audit.after_snapshot.get('resultHash')!=obj.result_hash
        or not BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',object_id=obj.pk,target_state='completed',
             operator_id=audit.actor_id,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}').exists()):
        raise ProductDesignError('TEST_CALCULATION_AUDIT_INVALID','测试核算保存人、权威审计或状态转换不一致。',409)
    valid=True;reason='当前批准、来源、规则及冻结输入有效。'
    try:
        validate_record_binding(obj)
        current=preview(user,t['context'])
        graph,_=rule_snapshot(user.company_id)
        if digest(graph)!=obj.rule_graph_hash or digest(current)!=obj.result_hash:
            raise ProductDesignError('TEST_CALCULATION_VERSION_CHANGED','当前输入、规则或单位依据与保存时不一致。',409)
    except (ProductDesignError,EngineeringCalculationError,ValidationError) as e:
        valid=False;reason=getattr(e,'message',str(e))
    return {'id':obj.pk,'calculationNo':obj.calculation_no,'statusLabel':'已保存测试核算','approvalScope':'TEST_BUSINESS',
        'baselineNo':obj.baseline.baseline_no,'designRevision':obj.design_revision.revision,'context':t['context'],
        'ruleSnapshot':t['ruleSnapshot'],'snapshot':frozen,'savedBy':t['savedBy'],'savedAt':obj.finished_at.isoformat(),
        'reason':t['reason'],'currentlyValid':valid,'validityLabel':'当前有效' if valid else '当前不可继续消费','validityReason':reason,
        'productionUseAllowed':False,'businessWriteSideEffectCount':0}

def consume_test(user,record_id):
    result=read_record(user,record_id)
    if not result['currentlyValid']:raise ProductDesignError('TEST_CALCULATION_NOT_EFFECTIVE',result['validityReason'],409)
    return result

@transaction.atomic
def _save(user,context,reason,key):
    authorize(user,True)
    if not reason.strip() or len(reason)>240:raise ProductDesignError('TEST_CALCULATION_REASON_REQUIRED','请填写240字以内的本次测试核算保存原因。')
    if set(context)!=set(FIELDS):raise ProductDesignError('TEST_CONTEXT_INVALID','保存必须明确完整精确上下文。',409)
    # Locks shared authority; no result from the client is accepted.
    from .models import OrderEngineeringBaseline,DesignRevisionApproval
    OrderEngineeringBaseline.objects.select_for_update().filter(pk=context['baselineId'],company_id=user.company_id).first()
    DesignRevisionApproval.objects.select_for_update().filter(pk=context['approvalId'],company_id=user.company_id).first()
    request,made,_=_write_request(user=user,action_code=ACTION,entity_type='TestBusinessCalculation',key=key,request_body={'context':context,'reason':reason})
    if not made:
        if not request.result.get('calculationId'):raise ProductDesignError('TEST_SAVE_IN_PROGRESS','同一保存请求尚未提交，请稍后读取。',409)
        return {**read_record(user,request.result['calculationId']),'idempotent':True}
    computed=preview(user,context)
    if not computed['calculationSucceeded']:raise ProductDesignError('TEST_CALCULATION_INCOMPLETE','当前资料尚不可计算，未保存任何核算。',409)
    graph,rule=rule_snapshot(user.company_id)
    b=baseline_for(user,context['baselineId']);_,item,_=context_for(user,b)
    input_snapshot={'context':context,'baselineHash':b.snapshot_hash,'itemHash':item.content_hash,'structuredInput':item.content_snapshot['revision']['designData']['calculationInputs']}
    now=timezone.now()
    obj=create_business_object_with_initial_state(model=EngineeringCalculationRecord,initial_state='running',company_id=user.company_id,
        scope='test_business',approval_scope='TEST_BUSINESS',baseline=b,design_revision_id=context['designRevisionId'],design_approval_id=context['approvalId'],
        source_record_id=context['sourceRecordId'],sales_order_item_id=context['salesOrderItemId'],engineering_instance_id=context['orderEngineeringInstanceId'],
        calculation_no=CodeRule.next_code(entity_type='production_engineering_calculation',company_id=user.company_id),
        rule_set_version=graph['adapterVersion'],idempotency_key=digest({'company':user.company_id,'testKey':key}),
        input_hash=digest(input_snapshot),rule_graph_hash=digest(graph),result_hash=digest(computed),started_at=now,
        trace={'context':context,'inputSnapshot':input_snapshot,'ruleSnapshot':graph,'resultSnapshot':computed,
               'savedBy':{'id':user.pk,'name':user.real_name,'username':user.username},'reason':reason})
    details=[]
    for seq,row in enumerate(computed['rows'],1):
        unit=UnitOfMeasure.objects.filter(company_id=user.company_id,code=row['unit'],is_active=True).first()
        if not unit:raise ProductDesignError('TEST_RESULT_UNIT_INVALID','结果单位无有效同公司定义。',409)
        d=EngineeringCalculationDetail.all_records.create(calculation=obj,sequence=seq,rule=rule,rule_code=rule.rule_code,rule_version=rule.version,
            expression_snapshot=row['expression'],input_snapshot={'componentKey':row['componentKey'],'inputs':row['inputs']},output_name=row['project'],
            output_value={'decimal':row['value']},uom=unit,precision=row['precision'],rounding=row['rounding'],status='succeeded',started_at=now,finished_at=timezone.now())
        details.append({'sequence':d.sequence,'ruleId':d.rule_id,'ruleCode':d.rule_code,'ruleVersion':d.rule_version,'expression':d.expression_snapshot,'inputs':d.input_snapshot,'output':d.output_value,'name':d.output_name,'uomId':d.uom_id,'precision':d.precision,'rounding':d.rounding})
    obj.trace['detailHash']=digest(details);obj.finished_at=timezone.now();obj.save(update_fields=['trace','finished_at'])
    audit=OrganizationOperatingAuditRecord.objects.create(actor=user,organization_id=user.company_id,action_code=ACTION,target_type='EngineeringCalculationRecord',target_id=obj.pk,target_label=obj.calculation_no,reason=reason,after_snapshot={'scope':'test_business','approvalScope':'TEST_BUSINESS','inputHash':obj.input_hash,'resultHash':obj.result_hash,'baselineId':b.pk})
    transition_business_object(business_object=obj,object_type='EngineeringCalculationRecord',source_state='running',target_state='completed',action_code=ACTION,operator=user,reason=reason,
       audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions=(('running','completed'),),version_field=None)
    _commit_request(request,{'calculationId':obj.pk,'targetId':obj.pk,'auditId':audit.pk})
    return {**read_record(user,obj.pk),'idempotent':False,'recordCreated':True,'businessWriteSideEffectCount':1+len(details)}

def save(user,context,reason,key):
    for attempt in range(8):
        try:return _save(user,context,reason,key)
        except (OperationalError,IntegrityError) as e:
            if isinstance(e,OperationalError) and 'locked' not in str(e).lower():raise
            if attempt==7:raise ProductDesignError('TEST_CALCULATION_BUSY','并发保存尚未完成，请使用原幂等键稍后重试。',409) from e
            sleep(.1*(attempt+1))

class TestCalculationPersistenceView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        try:
            data=dict(request.query_params.items())
            if set(data)=={'recordId'}:return Response(read_record(request.user,data['recordId']))
            if set(data)=={'baselineId'}:
                authorize(request.user)
                from .models import OrderEngineeringBaseline
                if not OrderEngineeringBaseline.objects.filter(pk=data['baselineId'],company_id=request.user.company_id).exists():
                    raise ProductDesignError('TEST_CONTEXT_NOT_FOUND','基线不存在或不可查看。',404)
                ids=EngineeringCalculationRecord.all_records.filter(company_id=request.user.company_id,scope='test_business',baseline_id=data['baselineId']).order_by('-pk').values_list('pk',flat=True)
                from system.authorization import AuthorizationService
                allowed=AuthorizationService.decide(user=request.user,action_code=ACTION,organization_id=request.user.company_id,business_object={'organizationId':request.user.company_id})['allowed']
                return Response({'records':[read_record(request.user,pk) for pk in ids],'canSave':allowed,'businessWriteSideEffectCount':0})
            raise ProductDesignError('TEST_CONTEXT_INVALID','请选择精确基线或已保存测试核算。')
        except (ProductDesignError,EngineeringCalculationError,ValidationError) as e:return self.error(e)
    def post(self,request):
        try:
            if set(request.data)!={'context','reason'}:raise ProductDesignError('TEST_SAVE_INPUT_NOT_ALLOWED','保存只接受精确上下文与原因，不接受结果或用途。',409)
            if not isinstance(request.data['context'],dict) or not isinstance(request.data['reason'],str):raise ProductDesignError('TEST_CONTEXT_INVALID','上下文须为明确对象，办理原因须为文字。')
            return Response(save(request.user,request.data['context'],str(request.data['reason']),request.headers.get('Idempotency-Key')))
        except (ProductDesignError,EngineeringCalculationError,ValidationError) as e:return self.error(e)
        except (ValueError,TypeError):return Response({'code':'TEST_CONTEXT_INVALID','message':'测试上下文格式不正确。'},status=400)
    @staticmethod
    def error(e):return Response({'code':getattr(e,'code','TEST_SNAPSHOT_INVALID'),'message':getattr(e,'message',str(e))},status=getattr(e,'http_status',403 if getattr(e,'code','')=='PERMISSION_DENIED' else 409))
