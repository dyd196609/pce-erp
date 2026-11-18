"""Consume an exact declaration approved by the existing design and CRM workflows."""
from decimal import Decimal
from .models import DesignRevisionApproval
from .design_revision_approval_service import effective
from .product_design_service import _canonical_hash
from planning.order_batch_service import fail, number

CONTRACT = 'PCE-FINISHED-SKU-SUBSTITUTION-V1'


def rate_value(value):
    from decimal import InvalidOperation
    try:
        rate=Decimal(str(value))
        if isinstance(value,bool) or not rate.is_finite() or rate<=0 or rate>=Decimal('1000000000000') or rate!=rate.quantize(Decimal('.000001')):
            raise ValueError()
        return rate
    except (InvalidOperation, ValueError, TypeError):
        fail('SUBSTITUTION_CONVERSION_INVALID','换算率必须为有依据的正数且不超过原换算精度，不得猜测或舍入。')


def validate_declaration(declaration, *, source=False, item=None):
    required={'contractVersion','substituteMaterialId','stockUomId','targetUomId','rangeStart','rangeEnd','targetPerStockUnit','conversionBasis'}
    if not source:required|={'salesOrderItemId','commercialReviewId'}
    if not isinstance(declaration,dict) or set(declaration)!=required or declaration['contractVersion']!=CONTRACT:
        fail('SUBSTITUTION_SCOPE_UNPROVEN','替代声明必须完整指定精确范围、产品单位、换算及批准来源。')
    for key in ('substituteMaterialId','stockUomId','targetUomId')+(() if source else ('salesOrderItemId','commercialReviewId')):
        if type(declaration[key]) is not int or declaration[key]<=0:
            fail('SUBSTITUTION_SCOPE_UNPROVEN','替代引用必须是明确的正式对象身份。')
    lo,hi=number(declaration['rangeStart'],zero=True),number(declaration['rangeEnd'])
    rate_value(declaration['targetPerStockUnit'])
    if lo>=hi or not isinstance(declaration['conversionBasis'],str) or not 0<len(declaration['conversionBasis'].strip())<=300:
        fail('SUBSTITUTION_SCOPE_UNPROVEN','替代范围或换算依据无效。')
    if item:
        from masterdata.models import Material, UnitOfMeasure
        if (declaration['salesOrderItemId']!=item.pk or hi>item.quantity or declaration['targetUomId']!=item.uom_id
            or not Material.objects.filter(pk=declaration['substituteMaterialId'],company_id=item.sales_order.company_id,is_active=True,material_type='finished',base_uom_id=declaration['stockUomId']).exists()
            or not UnitOfMeasure.objects.filter(pk=declaration['stockUomId'],company_id=item.sales_order.company_id,is_active=True).exists()):
            fail('SUBSTITUTION_SCOPE_MISMATCH','替代须属于本企业的准确订单行、有效产品和正式单位范围。')
    return declaration


def substitution_proof(*, item, approval_id, material_id, stock_uom_id, start, end, quantity):
    approval = DesignRevisionApproval.objects.select_related('source_record', 'sales_order_item',
        'final_decision__actor', 'source_revision').filter(pk=approval_id,
            company_id=item.sales_order.company_id, sales_order_item=item).first()
    if not approval or approval.approval_scope != 'PRODUCTION_USE':
        fail('SUBSTITUTION_APPROVAL_REQUIRED', '须有本企业本订单行的正式用途精确工程批准。')
    effective(approval)  # original process fingerprint, frozen content, actor/role SOD and authority
    declaration = approval.content_snapshot.get('revision', {}).get('designData', {}).get('finishedGoodsSubstitution')
    validate_declaration(declaration,item=item)
    if (declaration['contractVersion'] != CONTRACT or declaration['salesOrderItemId'] != item.pk
        or declaration['substituteMaterialId'] != material_id or declaration['stockUomId'] != stock_uom_id
        or declaration['targetUomId'] != item.uom_id or not str(declaration['conversionBasis']).strip()):
        fail('SUBSTITUTION_SCOPE_MISMATCH', '替代物料、单位、订单行或换算依据与批准不符。')
    lo, hi = number(declaration['rangeStart'], zero=True), number(declaration['rangeEnd'])
    rate = rate_value(declaration['targetPerStockUnit'])
    if not (0 <= lo <= start < end <= hi <= item.quantity) or quantity*rate != end-start:
        fail('SUBSTITUTION_CONVERSION_MISMATCH', '替代超出批准范围或不能按获准换算精确覆盖，禁止舍入或猜算。')
    # An engineering signature cannot approve a change in commercial promises.
    # Require the SAME declaration in the existing approved CRM source/scope;
    # old frozen sources are never edited to manufacture that approval.
    from .order_source_row_binding import approved_scope, rows_for_line
    relation, _, _ = approved_scope(approval.source_record, approval.engineering_instance)
    if relation.review_id != declaration['commercialReviewId']:
        fail('SUBSTITUTION_COMMERCIAL_APPROVAL_REQUIRED', '替代缺少准确原订单约定/变更批准范围。')
    rows = rows_for_line(approval.source_record, item, approval.engineering_instance)
    expected = {key:value for key,value in declaration.items() if key not in {'commercialReviewId','salesOrderItemId'}}
    if not any(row.get('finishedGoodsSubstitution') == expected for row in rows):
        fail('SUBSTITUTION_COMMERCIAL_APPROVAL_REQUIRED', '原订单批准冻结来源未包含同一替代约定；须先走原订单变更批准。')
    return {'contractVersion': CONTRACT, 'approvalId': approval.pk, 'decisionId': approval.final_decision_id,
        'applicantId': approval.applicant_id, 'approverId': approval.final_decision.actor_id,
        'contentHash': approval.content_hash, 'commercialReviewId': relation.review_id,
        'declarationHash': _canonical_hash(declaration), 'targetPerStockUnit': str(rate),
        'targetQuantity': str(end-start), 'stockQuantity': str(quantity)}
