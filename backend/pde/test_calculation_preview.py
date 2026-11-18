"""Read-only TEST_BUSINESS consumer; no state or calculation persistence."""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import OrderEngineeringBaseline, OrderEngineeringInstance
from .engineering_calculation_service import EngineeringCalculationService, EngineeringCalculationError
from .product_design_service import ProductDesignError
from .baseline_usage_service import validate_baseline
from .baseline_source_identity import resolve_baseline_source_identity

FIELDS = ('companyId','salesOrderId','salesOrderItemId','orderEngineeringInstanceId','baselineId',
          'designRevisionId','sourceRecordId','sourceVersion','sourceContentHash','sourceRowId','approvalId')

def baseline_for(user, baseline_id):
    EngineeringCalculationService._authorize(user=user, action_code='production.engineering.calculation.view', company_id=user.company_id)
    baseline = OrderEngineeringBaseline.objects.filter(pk=baseline_id,company_id=user.company_id).first()
    if not baseline: raise ProductDesignError('TEST_CONTEXT_NOT_FOUND','测试核算对象不存在或不可查看。',404)
    validate_baseline(baseline,purpose='TEST_BUSINESS')
    return baseline

def context_for(user, baseline):
    items=list(baseline.items.select_related('design_item__sales_order_item__sales_order','source_attribute','source_record','design_revision','baseline'))
    if len(items)!=1: raise ProductDesignError('TEST_SCOPE_UNSUPPORTED','当前测试预览要求明确选择单个冻结设计对象，不自动缩小基线范围。',409)
    item=items[0]; identity=resolve_baseline_source_identity(item)
    if identity['type']!='PCE_SOURCE_ROW_REVISION': raise ProductDesignError('TEST_SOURCE_CONTRACT_REQUIRED','该来源请沿用原有核算路径；本入口不替换Excel或USER_ENTRY。',409)
    instances=list(OrderEngineeringInstance.objects.filter(company_id=user.company_id,sales_order_item_id=identity['salesOrderItemId'],source_record_id=item.source_record_id))
    if len(instances)!=1: raise ProductDesignError('TEST_INSTANCE_NOT_UNIQUE','来源、订单行必须对应唯一工程实例。',409)
    approval=item.content_snapshot['approval']
    context={'companyId':user.company_id,'salesOrderId':baseline.sales_order_id,'salesOrderItemId':identity['salesOrderItemId'],
        'orderEngineeringInstanceId':instances[0].pk,'baselineId':baseline.pk,'designRevisionId':item.design_revision_id,
        'sourceRecordId':item.source_record_id,'sourceVersion':item.source_version_snapshot,
        'sourceContentHash':item.source_content_hash_snapshot,'sourceRowId':identity['sourceRowId'],'approvalId':approval['approvalId']}
    # Reuse admission/authorization consistency, without imposing design-complete or instance confirmation.
    from .design_revision_approval_service import current_exact
    from .models import DesignRevisionApproval
    bound_approval=DesignRevisionApproval.objects.get(pk=approval['approvalId'])
    if bound_approval.engineering_instance_id != instances[0].pk:
        raise ProductDesignError('TEST_CONTEXT_MISMATCH','批准关联工程实例不一致。',409)
    current_exact(bound_approval,require_current=False)
    return context,item,identity

def preview(user, data):
    baseline=baseline_for(user,data.get('baselineId'))
    context,item,identity=context_for(user,baseline)
    if set(data)!=set(FIELDS) or any(str(data.get(k))!=str(context[k]) for k in FIELDS):
        raise ProductDesignError('TEST_CONTEXT_MISMATCH','公司、订单、实例、基线、精确修订、来源版本/hash或批准绑定不一致。',409)
    # A cabinet assembly is not a panel. Existing THREE_IN_ONE formulas consume
    # explicit component inputs; do not turn outer dimensions or prose into parts.
    mapping=[
      {'field':'calculationInputs.ruleFamily','meaning':'明确采用三合一部件净量规则','unit':'条件','requiredWhen':'选择该柜体规则分支','value':None},
      {'field':'calculationInputs.components','meaning':'柜体拆分后的部件清单及各部件来源依据','unit':'清单','requiredWhen':'柜体整件尚未拆为板件','value':None},
      {'field':'components[].length','meaning':'部件长度→J，非柜体总高','unit':'mm','requiredWhen':'净面积及封边','value':None},
      {'field':'components[].width','meaning':'部件宽度→K','unit':'mm','requiredWhen':'净面积及封边','value':None},
      {'field':'components[].quantity','meaning':'部件订单总数量→M，只乘一次','unit':'明确计数单位→N','requiredWhen':'部件数量、净面积及封边','value':None},
      {'field':'components[].visibleCondition','meaning':'受治理见光条件→O','unit':'枚举','requiredWhen':'见光面积','value':None},
      {'field':'components[].edgeMethod','meaning':'受治理封边方式→P','unit':'枚举','requiredWhen':'结构封边净长度','value':None},
    ]
    from .calculation_batch_reuse import VERSION
    result={'statusLabel':'尚不可计算','sourceIdentityValid':True,'approvalPurposeValid':True,
       'inputComplete':False,'calculationSucceeded':False,'approvalScope':'TEST_BUSINESS',
       'context':context,'sourceIdentity':identity,'baselineNo':baseline.baseline_no,
       'designRevision':item.design_revision_no,'mapping':mapping,'rows':[],
       'blockers':[{'reason':'冻结R3没有结构化柜体部件输入及拆分依据；说明中的尺寸不作为运行输入。'},
                   {'reason':'整柜1套不能直接视为1块板。三合一部件映射须在新修订中明确并重新批准、新建基线。'}],
       'ruleEvidence':{'version':VERSION,'adapter':'calculation_batch_reuse.evaluate_row',
          'formulas':['部件数量=M','净面积=J*K*M/1000000','见光面积=J*K*M*受治理见光系数/1000000','封边净长=(J*长边数+K*宽边数)*M/1000'],
          'optional':'板厚L不参与上述净量表达式；材料、涂装、五金、玻璃及饰面不是这些结果的统一必填项。',
          'execution':'复用engineering_rule_foundation Decimal引擎；缺少获准部件输入时不执行。'},
       'businessWriteSideEffectCount':0,'factSource':'server'}
    inputs=(item.content_snapshot.get('revision',{}).get('designData') or {}).get('calculationInputs')
    if inputs:
        from .cabinet_calculation_adapter import calculate
        result.update(calculate(item,identity))
    return result

class TestCalculationPreviewView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        try:
            data=dict(request.query_params.items())
            if data=={'mode':'options'}:
                from .product_design_service import _authorize,ACTION_DESIGN_SAVE
                from .calculation_batch_reuse import EDGE_BRANCHES
                from .engineering_condition_options import VISIBLE_CONDITION_OPTIONS,visible_condition_multiplier
                from masterdata.models import UnitOfMeasure
                _authorize(request.user,ACTION_DESIGN_SAVE)
                return Response({'visibleConditions':[x['name'] for x in VISIBLE_CONDITION_OPTIONS if visible_condition_multiplier(x['name']) is not None],
                    'edgeMethods':list(EDGE_BRANCHES),'units':list(UnitOfMeasure.objects.filter(company_id=request.user.company_id,is_active=True,dimension__in=['length','count']).values('id','code','name','dimension'))})
            if data.get('mode')=='context':
                if set(data)!={'mode','baselineId'}: raise ProductDesignError('TEST_CONTEXT_INVALID','上下文读取参数不正确。')
                context,_,_=context_for(request.user,baseline_for(request.user,data['baselineId']))
                return Response({'context':context,'businessWriteSideEffectCount':0})
            return Response(preview(request.user,data))
        except (ProductDesignError,EngineeringCalculationError) as e:
            return Response({'code':e.code,'message':e.message,'details':getattr(e,'details',{})},status=getattr(e,'http_status',403 if e.code=='PERMISSION_DENIED' else 409))
        except (ValueError,TypeError):
            return Response({'code':'TEST_CONTEXT_INVALID','message':'测试上下文参数格式不正确。'},status=400)
