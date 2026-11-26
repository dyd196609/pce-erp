"""Explicit native Demand batches; quantities remain on Demand/Plan, not a coverage ledger."""
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from system.authorization import AuthorizationService
from system.models import User, OrganizationOperatingAuditRecord
from masterdata.models import MasterDataWriteRequest
from sales.models import SalesOrderItem
from sales.services import SalesBusinessError
from pde.product_design_service import _write_request, _commit_request, _canonical_hash
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object, record_projected_business_transition
from .models import Demand

CONTRACT = 'PCE-ORDER-MANUFACTURING-BATCH-V1'
PERMISSION = 'planning.production_plan.confirm'


def fail(code, message, status=409):
    raise SalesBusinessError(code, message, status)


def required_text(value, *, code, limit=300):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        fail(code, '必须提供明确且符合长度限制的文字依据或标识。', 400)
    return value.strip()


def number(value, *, zero=False):
    if isinstance(value, bool):
        fail('COVERAGE_QUANTITY_INVALID', '数量必须为明确的十进制数。')
    try:
        value = Decimal(str(value))
        if not value.is_finite() or value < 0 or (not zero and value == 0) or value != value.quantize(Decimal('.0001')) or value >= Decimal('100000000000000'):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        fail('COVERAGE_QUANTITY_INVALID', '数量必须在原数量精度内且为合法非负范围；不得舍入。')
    return value.quantize(Decimal('.0001'))


def actor_line(user, item_id, permission, *, lock=False):
    actor = User.objects.defer('password').filter(pk=getattr(user, 'pk', None), is_active=True).first()
    if not actor or actor.is_superuser or not actor.company_id:
        fail('COVERAGE_PERMISSION_DENIED', '须使用当前合法业务办理身份。', 403)
    rows = SalesOrderItem.objects.select_related('sales_order__department', 'material', 'uom')
    if lock:
        rows = rows.select_for_update()
    item = rows.filter(pk=item_id, sales_order__company_id=actor.company_id).first()
    if not item:
        fail('COVERAGE_ORDER_LINE_NOT_FOUND', '订单行不存在或不在当前企业范围。', 404)
    decision = AuthorizationService.decide(user=actor, action_code=permission,
        organization_id=actor.company_id,
        business_object={'organizationId': actor.company_id, 'departmentId': item.sales_order.department_id,
            'createdById': item.sales_order.created_by_id, 'salesOrderId': item.sales_order_id})
    if not decision.get('allowed'):
        fail('COVERAGE_PERMISSION_DENIED', '缺少本订单范围的原业务办理权限。', 403)
    return actor, item, decision


def line_identity(item):
    return {'companyId': item.sales_order.company_id, 'salesOrderId': item.sales_order_id,
        'salesOrderItemId': item.pk, 'materialId': item.material_id, 'uomId': item.uom_id,
        'approvedQuantity': str(item.quantity), 'requiredDate': item.required_date.isoformat()}


def range_values(item, start, end):
    start, end = number(start, zero=True), number(end)
    if not item.uom_id or item.uom.company_id!=item.sales_order.company_id or not item.uom.is_active:
        fail('COVERAGE_UNIT_UNPROVEN','本订单行缺少有效的同企业正式数量单位。')
    quantum=Decimal(1).scaleb(-item.uom.decimal_places)
    if start!=start.quantize(quantum) or end!=end.quantize(quantum):
        fail('COVERAGE_UNIT_PRECISION_INVALID','本范围不符合原正式单位数量精度，不能舍入或拆成非法数量。')
    if start >= end or end > item.quantity:
        fail('COVERAGE_RANGE_INVALID', '覆盖范围必须属于本订单行已批准数量，起点小于终点。')
    return start, end


def verify_batch(demand):
    """Validate the immutable native creation audit, never infer a batch from time."""
    if not demand.batch_key:
        if demand.batch_scope:
            fail('BATCH_SOURCE_UNPROVEN', '旧需求不得凭非正式JSON声称分批范围。')
        return None
    item = demand.sales_order_item
    scope = dict(demand.batch_scope)
    audit_id = scope.pop('auditId', None)
    event = OrganizationOperatingAuditRecord.objects.filter(pk=audit_id, organization_id=item.sales_order.company_id,
        action_code=PERMISSION, target_type='Demand', target_id=demand.pk).first()
    if not event or event.after_snapshot.get('batchScope') != scope or not event.after_snapshot.get('authorization', {}).get('allowed'):
        fail('BATCH_AUDIT_UNPROVEN', '批次缺少一致的原生范围登记审计。')
    for key, value in line_identity(item).items():
        if scope.get(key) != value:
            fail('BATCH_SOURCE_CHANGED', '批次绑定的订单行、单位或批准数量已变化。')
    start, end = range_values(item, scope.get('rangeStart'), scope.get('rangeEnd'))
    if (scope.get('contractVersion') != CONTRACT or scope.get('batchKey') != demand.batch_key
        or scope.get('manufacturingOutputId') != demand.manufacturing_output_id
        or demand.required_qty != end-start or demand.material_id != item.material_id
        or demand.department.company_id != item.sales_order.company_id or demand.department_id!=item.sales_order.department_id
        or demand.required_date != item.required_date
        or demand.source_type != 'sales_order' or demand.source_document_type != 'SalesOrderItem'
        or demand.source_document_id != str(item.pk)):
        fail('BATCH_SOURCE_UNPROVEN', '批次数量、来源或范围不一致。')
    request = MasterDataWriteRequest.objects.filter(pk=scope.get('writeRequestId'), status='COMMITTED',
        organization_id=item.sales_order.company_id, entity_type='DemandBatch', action_code=PERMISSION).first()
    if (not request or request.result.get('demandId') != demand.pk or request.result.get('auditId') != audit_id
        or request.result.get('batchScope')!=scope or request.request_hash!=_canonical_hash(request.audit_metadata)):
        fail('BATCH_AUDIT_UNPROVEN', '批次缺少原生提交结果。')
    from workflow_runtime.models import BusinessStateTransition
    confirmations=list(BusinessStateTransition.objects.filter(object_type='Demand',object_id=demand.pk,
        source_state='draft',target_state='confirmed',action_code=PERMISSION))
    if len(confirmations)!=1 or not OrganizationOperatingAuditRecord.objects.filter(
        pk=int(confirmations[0].audit_reference.split(':')[-1]),organization_id=item.sales_order.company_id,
        target_type='Demand',target_id=demand.pk,action_code=PERMISSION,
        after_snapshot__batchScopeAuditId=audit_id,after_snapshot__authorization__allowed=True).exists():
        fail('BATCH_STATE_UNPROVEN','分批需求缺少原生确认和准确范围审计。')
    active=True
    if demand.status=='closed':
        from workflow_runtime.models import BusinessStateTransition
        events=OrganizationOperatingAuditRecord.objects.filter(organization_id=item.sales_order.company_id,
            target_type='Demand',target_id=demand.pk,action_code=PERMISSION,
            after_snapshot__batchCancelled=True,after_snapshot__originalAuditId=audit_id)
        event=events.first()
        if (events.count()!=1 or not event.after_snapshot.get('authorization',{}).get('allowed')
            or not BusinessStateTransition.objects.filter(object_type='Demand',object_id=demand.pk,
                source_state='confirmed',target_state='closed',audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}').exists()
            or hasattr(demand,'planning_requirement')):
            fail('BATCH_CANCELLATION_UNPROVEN','批次关闭缺少未投入取消和原生审计，不能静默排除历史。')
        active=False
    elif demand.status!='confirmed':
        fail('BATCH_STATE_UNPROVEN','批次缺少有效确认状态。')
    if active:
        from sales.manufacturing_input import resolve_demand_manufacturing_input
        source=resolve_demand_manufacturing_input(item,supply_branch='MAKE',output_id=demand.manufacturing_output_id)
        if scope.get('manufacturingSource')!=source['facts']:
            fail('BATCH_SOURCE_CHANGED','批次冻结制造来源已变化。')
    return {'demandId': demand.pk, 'rangeStart': str(start), 'rangeEnd': str(end),
        'quantity': str(end-start), 'uomId': item.uom_id, 'auditId': audit_id, 'active': active,
        'manufacturingOutputId': demand.manufacturing_output_id, 'batchKey': demand.batch_key}


def assert_free_range(item, start, end):
    for demand in Demand.objects.select_for_update().filter(sales_order_item=item).select_related('department'):
        proof = verify_batch(demand)
        if proof is None:
            fail('BATCH_LEGACY_SCOPE_REVIEW_REQUIRED', '已有未分批历史需求，须通过原正式更正核定剩余范围，不得覆盖或猜分历史。')
        if not proof['active']:continue
        if start < number(proof['rangeEnd']) and number(proof['rangeStart'], zero=True) < end:
            fail('COVERAGE_RANGE_OVERLAP', '本范围已被有效制造批次覆盖；不能新旧双计。')
    from procurement.order_stock_allocation import allocations_for_line
    for allocation in allocations_for_line(item, lock=True):
        if start < number(allocation['rangeEnd']) and number(allocation['rangeStart'], zero=True) < end:
            fail('COVERAGE_RANGE_OVERLAP', '本范围已有有效库存分配，不得重复制造覆盖。')


def action_result(*, user, item_id, entity_type, key, allocation_id=None, demand_id=None):
    permission = PERMISSION if entity_type in {'DemandBatch','DemandBatchCancel'} else 'warehouse.production.putaway'
    actor,item,_ = actor_line(user,item_id,permission)
    if not key or len(str(key))>160:
        fail('COVERAGE_RESULT_KEY_REQUIRED','请保留并提供同一次原动作的幂等键。',400)
    row=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,
        action_code=permission,entity_type=entity_type,idempotency_key=key).first()
    if row:
        body=row.audit_metadata
        in_scope=body.get('itemIds')==[item.pk] if allocation_id is None else body.get('allocationId')==allocation_id
        if demand_id is not None:in_scope=in_scope and body.get('demandId')==demand_id
        if not in_scope:
            fail('COVERAGE_RESULT_NOT_FOUND','该动作不属于本查看对象。',404)
    return {'resultState':'COMMITTED' if row and row.status=='COMMITTED' else 'UNKNOWN',
        'sameActionKey':str(key),'result':row.result if row and row.status=='COMMITTED' else None,
        'automaticReplayAllowed':False,'businessWriteCount':0}


@transaction.atomic
def cancel_batch(*,user,item_id,demand_id,payload,key):
    actor,item,decision=actor_line(user,item_id,PERMISSION,lock=True)
    demand=Demand.objects.select_for_update().filter(pk=demand_id,sales_order_item=item).first()
    if not demand:fail('BATCH_NOT_FOUND','批次不属于当前订单行。',404)
    if (not isinstance(payload, dict) or set(payload)!={'expectedAuditId','reason'}
        or type(payload['expectedAuditId']) is not int or payload['expectedAuditId']<=0):
        fail('BATCH_CANCEL_INPUT_INVALID','须明确原登记审计和取消依据。',400)
    required_text(payload['reason'], code='BATCH_CANCEL_INPUT_INVALID')
    request,created,_=_write_request(user=actor,action_code=PERMISSION,entity_type='DemandBatchCancel',key=key,
        request_body={'orderId':item.sales_order_id,'itemIds':[item.pk],'demandId':demand.pk,**payload})
    if not created and request.status=='COMMITTED':return {**request.result,'idempotent':True}
    proof=verify_batch(demand)
    if (not proof or not proof['active'] or proof['auditId']!=payload['expectedAuditId']
        or hasattr(demand,'planning_requirement') or item.sales_order.status in {'completed','closed'}):
        fail('BATCH_CANCEL_DOWNSTREAM_BLOCKED','仅未投入、无计划且原登记未变化的分批可取消；已有计划/执行须走原正式更正机制。')
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,
        action_code=PERMISSION,target_type='Demand',target_id=demand.pk,target_label=demand.demand_no,
        reason=payload['reason'],before_snapshot={'status':demand.status},after_snapshot={
            'batchCancelled':True,'originalAuditId':proof['auditId'],'authorization':decision})
    transition_business_object(business_object=demand,object_type='Demand',source_state='confirmed',target_state='closed',
        action_code=PERMISSION,operator=actor,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('confirmed','closed')},version_field=None)
    result={'demandId':demand.pk,'auditId':event.pk,'idempotent':False}
    _commit_request(request,result);return result


@transaction.atomic
def create_batch(*, user, item_id, payload, key):
    actor, item, decision = actor_line(user, item_id, PERMISSION, lock=True)
    allowed = {'batchKey', 'manufacturingOutputId', 'rangeStart', 'rangeEnd', 'reason'}
    if not isinstance(payload, dict) or set(payload) != allowed:
        fail('BATCH_INPUT_INVALID', '必须明确批次、制造来源、范围和登记依据，不得提交状态。', 400)
    from sales.supply_admission_service import supply_admission_facts
    if supply_admission_facts(item)['supplyBranch'] != 'MAKE':
        fail('BATCH_NOT_APPLICABLE', '分批制造仅适用于原合同自制订单行。')
    if item.sales_order.status not in {'confirmed','approved','engineering','manufacturing_ready','in_progress'}:
        fail('BATCH_ORDER_STATE_INVALID', '当前订单状态不允许新增制造覆盖。')
    batch_key = required_text(payload['batchKey'], code='BATCH_INPUT_INVALID', limit=80)
    reason = required_text(payload['reason'], code='BATCH_INPUT_INVALID')
    start, end = range_values(item, payload['rangeStart'], payload['rangeEnd'])
    from sales.manufacturing_input import resolve_demand_manufacturing_input
    from sales.services import engineering_readiness_facts
    from pde.models import ManufacturingInputReference
    source = resolve_demand_manufacturing_input(item, supply_branch='MAKE', output_id=payload['manufacturingOutputId'])
    readiness = engineering_readiness_facts(item.sales_order, manufacturing_output_ids={item.pk: payload['manufacturingOutputId']})
    line = next((x for x in readiness['lines'] if x['salesOrderItemId']==item.pk), None)
    if not line or not line['ready'] or not source['output']:
        fail('BATCH_MANUFACTURING_NOT_READY', '该批来源尚未通过原制造准备准入。')
    body = {'orderId': item.sales_order_id, 'itemIds': [item.pk], **payload}
    request, created, _ = _write_request(user=actor, action_code=PERMISSION, entity_type='DemandBatch', key=key, request_body=body)
    if not created and request.status=='COMMITTED':
        existing=Demand.objects.get(pk=request.result['demandId']);verify_batch(existing)
        return {**request.result, 'idempotent': True}
    if Demand.objects.filter(sales_order_item=item, batch_key=batch_key).exists():
        fail('BATCH_KEY_CONFLICT', '该订单行批次标识已存在，须查询原动作结果。')
    assert_free_range(item, start, end)
    scope = {**line_identity(item), 'contractVersion': CONTRACT, 'batchKey': batch_key,
        'rangeStart': str(start), 'rangeEnd': str(end), 'manufacturingOutputId': source['output'].pk,
        'manufacturingSource': source['facts'], 'writeRequestId': request.pk, 'reason': reason}
    demand = create_business_object_with_initial_state(model=Demand, initial_state='draft',
        demand_no=f'BATCH-{request.pk}', batch_key=batch_key, batch_scope={}, source_type='sales_order',
        source_document_type='SalesOrderItem', source_document_id=str(item.pk), source_document_no=item.sales_order.order_no,
        sales_order_item=item, product_definition=item.product_definition, product_version=item.product_version,
        manufacturing_output=source['output'], material=item.material, required_qty=end-start, required_date=item.required_date,
        department=item.sales_order.department, reason=reason, created_by=actor)
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor, organization_id=actor.company_id,
        action_code=PERMISSION, target_type='Demand', target_id=demand.pk, target_label=demand.demand_no,
        reason=reason, after_snapshot={'batchScope': scope, 'authorization': decision})
    demand.batch_scope={**scope, 'auditId': event.pk};demand.save(update_fields=['batch_scope'])
    record_projected_business_transition(object_type='Demand', object_id=demand.pk, source_state='', target_state='draft',
        action_code=PERMISSION, operator=actor, reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}', allowed_transitions={('', 'draft')})
    confirmation=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,
        action_code=PERMISSION,target_type='Demand',target_id=demand.pk,target_label=demand.demand_no,
        reason=reason,before_snapshot={'status':'draft'},after_snapshot={'status':'confirmed',
            'batchScopeAuditId':event.pk,'authorization':decision})
    transition_business_object(business_object=demand, object_type='Demand', source_state='draft', target_state='confirmed',
        action_code=PERMISSION, operator=actor, reason=reason, audit_reference=f'OrganizationOperatingAuditRecord:{confirmation.pk}', allowed_transitions={('draft','confirmed')},version_field=None)
    ManufacturingInputReference.objects.create(target_module='MRP', source_object=f'ProductManufacturingOutput:{source["output"].pk}',
        target_object=f'Demand:{demand.pk}', source_manufacturing_output=source['output'], target_demand=demand, reference_status='active')
    result={'demandId': demand.pk, 'auditId': event.pk, 'batchScope': scope, 'idempotent': False}
    _commit_request(request, result)
    verify_batch(demand)
    return result
