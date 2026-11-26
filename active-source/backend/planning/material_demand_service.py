"""Explicit production-material source handoff on the original Demand authority.

No availability deduction, procurement, reservation or issue is performed here.
ExternalIdentity carries typed immutable provenance, not another quantity ledger.
"""
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import ValidationError
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import User, Company, OrganizationOperatingAuditRecord
from system.authorization import AuthorizationService
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition, transition_business_object
from .models import Demand, ProductionPlan
from .services import PlanningBusinessError, _number

CONTRACT = 'PCE-PRODUCTION-MATERIAL-DEMAND-V1'
SOURCE = 'production_material'
CREATE = 'planning.demand.create'
# The original native manufacturing-batch service confirms Demand with this
# existing permission. Creation alone never grants that confirmation authority.
CONFIRM = 'planning.production_plan.confirm'
ENTITY = 'ProductionMaterialDemand'
SYSTEM = 'PCE_PRODUCTION_MATERIAL_DEMAND'
SOURCE_EXPECTATION_UNSET = object()


def fail(code, message, status=409):
    raise PlanningBusinessError(code, message, http_status=status)


def _intent(payload,key):
    reason=payload.get('reason') if isinstance(payload,dict) else None
    if not isinstance(reason,str) or not reason.strip() or len(reason)>300 or not isinstance(key,str) or not key.strip() or len(key)>160:
        fail('MATERIAL_DEMAND_INPUT_INVALID','须提供明确办理理由（不超过300字）和原同次动作键（不超过160字）。',400)


def _own_receipt(request,actor):
    demand=Demand.objects.filter(pk=request.result.get('demandId'),source_type=SOURCE,department__company_id=actor.company_id).first()
    if not demand or not OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('auditId'),actor=actor,
            action_code=request.action_code,target_type='Demand',target_id=demand.pk,organization_id=actor.company_id).exists():
        fail('MATERIAL_RESULT_NOT_FOUND','同次动作不属于当前办理人。',404)
    verify_demand(demand,current=False)
    return {**request.result,'idempotent':True,'historicalReceiptOnly':True}


def _fact_quantity_equals(value,expected):
    try:
        actual=Decimal(str(value))
        return actual.is_finite() and actual==expected
    except (InvalidOperation,ValueError,TypeError):
        return False


def decimal(value, *, zero=False):
    if isinstance(value, bool):
        fail('MATERIAL_SOURCE_QUANTITY_INVALID', '数量必须为准确十进制值。', 400)
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or (not zero and n == 0):
            raise ValueError()
        return n
    except (InvalidOperation, ValueError, TypeError):
        fail('MATERIAL_SOURCE_QUANTITY_INVALID', '数量必须为准确的非负范围。', 400)


def actor_plan(user, plan_id, permission, *, lock=False):
    actor = User.objects.defer('password').filter(pk=getattr(user, 'pk', None), is_active=True).first()
    if not actor or actor.is_superuser or not actor.company_id:
        fail('MATERIAL_DEMAND_PERMISSION_DENIED', '须使用原有效范围的合法业务身份。', 403)
    from pfm.formal_employee import formal_employee_queryset
    if not formal_employee_queryset(company_id=actor.company_id).filter(user_id=actor.pk).exists():
        fail('MATERIAL_DEMAND_EMPLOYEE_REQUIRED','须使用原在职员工及有效组织岗位链；账号角色本身不替代正式办理身份。',403)
    if type(plan_id) is not int or plan_id <= 0:
        fail('MATERIAL_PRODUCTION_SCOPE_REQUIRED', '须选择准确已批准生产计划。', 400)
    if lock:
        Company.objects.select_for_update().get(pk=actor.company_id)
    rows = ProductionPlan.objects.select_related('planning_requirement__demand__department',
        'planning_requirement__demand__sales_order_item__sales_order',
        'planning_requirement__demand__sales_order_item__uom',
        'planning_requirement__demand__manufacturing_output__bom_version')
    if lock:
        rows = rows.select_for_update()
    plan = rows.filter(pk=plan_id, planning_requirement__demand__department__company_id=actor.company_id).first()
    if not plan:
        fail('MATERIAL_PRODUCTION_PLAN_NOT_FOUND', '生产对象不存在或不在本企业范围。', 404)
    d = plan.planning_requirement.demand
    item = d.sales_order_item
    from .services import _plan_start_decision
    decision = _plan_start_decision(actor, plan, permission)
    if not decision.get('allowed'):
        fail('MATERIAL_DEMAND_PERMISSION_DENIED', '缺少本对象范围的原办理或读取资格。', 403)
    return actor, plan, decision


def _approved_scope(plan):
    d = plan.planning_requirement.demand
    requirement=plan.planning_requirement
    item = d.sales_order_item
    if not (item and item.uom_id and plan.status == 'confirmed' and d.status == 'confirmed'
            and plan.planned_qty > 0 and plan.planned_qty <= d.required_qty
            and plan.material_id == d.material_id == item.material_id
            and requirement.material_id==d.material_id and requirement.supply_type=='production'
            and requirement.demand_qty==d.required_qty and requirement.net_required_qty==plan.planned_qty
            and d.source_type=='sales_order' and d.source_document_type=='SalesOrderItem'
            and d.source_document_id==str(item.pk) and d.source_document_no==item.sales_order.order_no
            and d.department.company_id==item.sales_order.company_id==d.material.company_id
            and item.sales_order.status in {'approved','confirmed','engineering','manufacturing_ready','in_progress','delivering'}):
        fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN', '尚无准确有效的原需求、订单及批准生产范围。')
    transitions = list(BusinessStateTransition.objects.filter(object_type='ProductionPlan',object_id=plan.pk,
        source_state='draft',target_state='confirmed',action_code=CONFIRM))
    if len(transitions) != 1:
        fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN', '生产计划缺少唯一原生确认事实。')
    t = transitions[0]
    event = OrganizationOperatingAuditRecord.objects.filter(organization_id=d.department.company_id,
        target_type='ProductionPlan',target_id=plan.pk,action_code=CONFIRM,
        pk=_audit_id(t.audit_reference)).first()
    snapshot=event.after_snapshot if event and isinstance(event.after_snapshot,dict) else {}
    state=snapshot.get('state',{})
    if not event or not snapshot.get('authorization',{}).get('allowed') or not isinstance(state,dict) or not _fact_quantity_equals(state.get('planQty'),plan.planned_qty) or state.get('sourceRequirementId')!=plan.planning_requirement_id or state.get('demandId')!=d.pk:
        fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN', '生产范围与原生确认审计不一致。')
    if d.batch_key:
        from .order_batch_service import verify_batch
        proof = verify_batch(d)
        start, end = decimal(proof['rangeStart'],zero=True), decimal(proof['rangeEnd'])
        if end-start != plan.planned_qty:
            fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN', '分批计划缺少准确子范围。')
    else:
        demand_confirmations=list(BusinessStateTransition.objects.filter(object_type='Demand',object_id=d.pk,
            source_state='draft',target_state='confirmed',action_code='sales.order.generate_demand'))
        parent_event=OrganizationOperatingAuditRecord.objects.filter(pk=_audit_id(demand_confirmations[0].audit_reference),
            organization_id=d.department.company_id,target_type='Demand',target_id=d.pk,
            action_code='sales.order.generate_demand',actor_id=d.created_by_id).first() if len(demand_confirmations)==1 else None
        parent_snapshot=parent_event.after_snapshot if parent_event and isinstance(parent_event.after_snapshot,dict) else {}
        parent_state=parent_snapshot.get('state',{})
        if not parent_event or not parent_snapshot.get('authorization',{}).get('allowed') or not isinstance(parent_state,dict) or parent_state.get('salesOrderItemId')!=item.pk or not _fact_quantity_equals(parent_state.get('requiredQty'),d.required_qty):
            fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN','原订单需求缺少准确确认、数量及真实审计证明。')
        if d.required_qty != item.quantity or plan.planned_qty != item.quantity:
            fail('MATERIAL_PRODUCTION_SCOPE_UNPROVEN', '旧部分数量无准确范围证明，不默认整单或猜配剩余。')
        start, end = Decimal('0'), item.quantity
    return item, start, end, event.pk


def _audit_id(reference):
    if not str(reference).startswith('OrganizationOperatingAuditRecord:'):
        return None
    try:
        return int(reference.split(':')[1])
    except (ValueError, IndexError):
        return None


def _production_source_context(*, plan, selection, require_line=True):
    """Original approved range and released source gate for selection and writes."""
    from sales.manufacturing_input import resolve_demand_manufacturing_input
    item, approved_start, approved_end, plan_audit = _approved_scope(plan)
    required={'rangeStart','rangeEnd'}|({'sourceObjectType','sourceLineId'} if require_line else set())
    if not required <= set(selection):
        fail('MATERIAL_SOURCE_SELECTION_REQUIRED', '须明确来源对象类型、明细及本次生产范围。', 400)
    start, end = decimal(selection['rangeStart'],zero=True), decimal(selection['rangeEnd'])
    quantum = Decimal(1).scaleb(-item.uom.decimal_places)
    if not (approved_start <= start < end <= approved_end) or start != start.quantize(quantum) or end != end.quantize(quantum):
        fail('MATERIAL_PRODUCTION_RANGE_INVALID', '范围不属于准确批准生产量或不符合原单位精度。')
    native = resolve_demand_manufacturing_input(item, supply_branch='MAKE', output_id=plan.planning_requirement.demand.manufacturing_output_id)
    output = native['output']
    if not output or output.release_status != 'released_to_manufacturing':
        fail('MATERIAL_ENGINEERING_NOT_RELEASED', '原正式工程制造来源未发布。')
    version = output.bom_version
    if not version or version.status != 'released' or version.usage_purpose != 'PRODUCTION_USE':
        fail('MATERIAL_ENGINEERING_NOT_RELEASED', '须采用准确已发布正式用途BOM版本。')
    return item, approved_start, approved_end, plan_audit, start, end, native, output, version


def resolve_source(*, actor, plan, selection, _resolved_context=None):
    from pde.models import BOMItem, EngineeringMaterialRequirement, BOMItemSourceRequirement
    # Only the atomic catalogue read supplies its own already-proved context.
    # Original preview/registration/confirmation callers always recompute it.
    item, approved_start, approved_end, plan_audit, start, end, native, output, version = (
        _production_source_context(plan=plan,selection=selection) if _resolved_context is None else _resolved_context)
    source_type = selection['sourceObjectType']
    line_id = selection['sourceLineId']
    if type(line_id) is not int or line_id <= 0:
        fail('MATERIAL_SOURCE_LINE_INVALID', '须提供准确来源行身份。', 400)
    req = None
    if source_type == 'EngineeringMaterialRequirement':
        req = EngineeringMaterialRequirement.objects.select_related('calculation','source_detail','material','uom').filter(
            pk=line_id,calculation__company_id=actor.company_id).first()
        link = BOMItemSourceRequirement.objects.select_related('bom_item').filter(material_requirement=req,bom_item__bom_version=version).first() if req else None
        if not req or not link:
            fail('MATERIAL_SOURCE_RELATION_UNPROVEN', '工程原料行与本次已发布BOM缺少准确原生关联。')
        bom_item = link.bom_item
    elif source_type == 'BOMItem':
        bom_item = BOMItem.objects.select_related('material','uom').filter(pk=line_id,bom_version=version).first()
        if not bom_item:
            fail('MATERIAL_SOURCE_LINE_NOT_FOUND', '来源行不属于本次准确发布版本。', 404)
    else:
        fail('MATERIAL_SOURCE_TYPE_INVALID', '来源必须为明确的工程材料需求行或BOM行。', 400)
    source_number=req.calculation.calculation_no if req else (version.bom.bom_code if version.bom_id else None)
    if not source_number or len(source_number)>Demand._meta.get_field('source_document_no').max_length:
        fail('MATERIAL_SOURCE_NUMBER_UNPROVEN','来源正式工程核算编号或BOM编号未提供，不能用生产计划号或内部ID冒充。')
    if not bom_item.is_active or bom_item.item_role != 'material' or (bom_item.effective_from and bom_item.effective_from>plan.required_date) or (bom_item.effective_to and bom_item.effective_to<plan.required_date):
        fail('MATERIAL_SOURCE_LINE_INACTIVE', '本次日期或原料行不适用。')
    material, uom = bom_item.material, bom_item.uom
    if not (material.company_id == uom.company_id == actor.company_id and material.is_active and uom.is_active):
        fail('MATERIAL_SOURCE_UNIT_UNPROVEN', '原物料或来源单位的归属、启用状态未获证明。')
    links = list(BOMItemSourceRequirement.objects.select_related('material_requirement__calculation','material_requirement__source_detail').filter(bom_item=bom_item))
    if version.source_calculation_id and (not links or sum((x.contributed_quantity for x in links),Decimal('0')) != bom_item.quantity):
        fail('MATERIAL_SOURCE_QUANTITY_UNPROVEN', 'BOM贡献量或原工程明细证明不完整。')
    members=[]
    for link in links:
        r=link.material_requirement;c=r.calculation
        if not (c.pk==version.source_calculation_id and c.status=='completed' and c.company_id==actor.company_id
                and c.sales_order_item_id==item.pk and r.source_detail.calculation_id==c.pk
                and r.material_id==material.pk and r.uom_id==uom.pk and r.order_quantity==item.quantity
                and link.contributed_quantity==r.net_quantity):
            fail('MATERIAL_SOURCE_RELATION_UNPROVEN', '工程明细、订单行、版本、单位或贡献数量不一致。')
        members.append({'type':'EngineeringMaterialRequirement','id':r.pk,'calculationId':c.pk,
            'resultHash':c.result_hash,'sourceDetailId':r.source_detail_id,'basis':r.quantity_basis,
            'calculatedQuantity':str(r.calculated_quantity),'orderQuantity':str(r.order_quantity),
            'netQuantity':str(r.net_quantity),'grossQuantity':str(r.gross_quantity) if r.gross_quantity is not None else None,
            'scrapRateStatus':r.scrap_rate_status,'scrapRate':str(r.scrap_rate) if r.scrap_rate is not None else None})
    selected = [x for x in links if req is None or x.material_requirement_id==req.pk]
    atoms=[f'EngineeringMaterialRequirement:{x.material_requirement_id}' for x in selected] or [f'BOMItem:{bom_item.pk}']
    # Geometry is checked from native typed links even if ORDER_TOTAL itself
    # has no lawful proportional split. Do not misdescribe overlap as shortage.
    for identity in ExternalIdentity.objects.filter(organization_id=actor.company_id,source_system=SYSTEM,source_object_type=ENTITY):
        old=(identity.audit_metadata or {}).get('sourceProof',{})
        if old.get('salesOrderItemId')!=item.pk or not set(atoms)&set(old.get('sourceAtoms',[])):continue
        a,b=decimal(old.get('rangeStart'),zero=True),decimal(old.get('rangeEnd'))
        if start<b and a<end and (start,end)!=(a,b):
            verify_demand(Demand.objects.get(pk=identity.target_entity_id),current=False)
            fail('MATERIAL_DEMAND_RANGE_OVERLAP','本次子范围与已登记的准确原生用料范围重叠，不能重复计量。')
    quantity=Decimal('0');basis=[]
    if selected:
        for link in selected:
            r=link.material_requirement
            if r.scrap_rate_status!='maintained' or r.scrap_rate is None or r.gross_quantity is None:
                fail('MATERIAL_QUANTITY_BASIS_MISSING', '工程损耗或含损耗数量未维护，保持未知，不能补零。')
            if r.quantity_basis=='ORDER_TOTAL':
                if start!=0 or end!=item.quantity:
                    fail('MATERIAL_TOTAL_SCOPE_NOT_DIVISIBLE', '原工程整单总量无子范围分摊合同，不能按比例猜分。')
                q=r.gross_quantity
            elif r.quantity_basis=='PER_SALES_ITEM_UNIT':
                # Original engineering/APPLY_ONCE and native MRP scrap rules.
                q=r.calculated_quantity*(end-start)/(Decimal('1')-r.scrap_rate)
                if r.net_quantity != r.calculated_quantity*item.quantity:
                    fail('MATERIAL_SOURCE_QUANTITY_UNPROVEN','工程单位用量与原整单核定量不一致。')
            else:
                fail('MATERIAL_QUANTITY_BASIS_MISSING','工程数量口径未提供。')
            quantity+=q;basis.append(r.quantity_basis)
    else:
        if bom_item.quantity_rule:
            fail('MATERIAL_QUANTITY_RULE_UNSUPPORTED','本BOM另有正式参数规则，须复用其正式结果，不按常量猜算。')
        if bom_item.scrap_rate_status!='maintained' or bom_item.scrap_rate is None:
            fail('MATERIAL_QUANTITY_BASIS_MISSING','BOM损耗率未维护，禁止默认补零。')
        quantity=(end-start)*bom_item.quantity/(Decimal('1')-bom_item.scrap_rate)
        basis=['NATIVE_MRP_BOM_PER_PRODUCTION_UNIT']
    field=Demand._meta.get_field('required_qty');precision=Decimal(1).scaleb(-field.decimal_places)
    if quantity<=0 or quantity>=Decimal(10)**(field.max_digits-field.decimal_places) or quantity!=quantity.quantize(precision):
        fail('MATERIAL_DEMAND_PRECISION_UNSUPPORTED','原Demand数量精度不能无损承载来源量，禁止静默舍入；须核定最小结构差异。')
    if quantity!=quantity.quantize(Decimal(1).scaleb(-uom.decimal_places)):
        fail('MATERIAL_SOURCE_UNIT_PRECISION_INVALID','来源量不符合原正式计量单位精度，字段6位不扩大单位适用范围。')
    proof={'contractVersion':CONTRACT,'companyId':actor.company_id,'productionPlanId':plan.pk,'productionPlanNo':plan.plan_no,
        'productionPlanAuditId':plan_audit,'parentDemandId':plan.planning_requirement.demand_id,
        'salesOrderId':item.sales_order_id,'salesOrderItemId':item.pk,'productionUomId':item.uom_id,
        'approvedRangeStart':str(approved_start),'approvedRangeEnd':str(approved_end),'rangeStart':str(start),'rangeEnd':str(end),
        'manufacturingOutputId':output.pk,'manufacturingSource':native['facts'],'bomVersionId':version.pk,
        'bomVersion':version.bom_version,'bomRevision':version.revision,'bomItemId':bom_item.pk,
        'sourceObjectType':source_type,'sourceLineId':line_id,'sourceMembers':members,'sourceAtoms':atoms,
        'sourceDocumentNo':source_number,
        'materialId':material.pk,'materialCode':material.code,'materialName':material.name,
        'uomId':uom.pk,'uomCode':uom.code,'quantityBasis':basis,'requiredQty':str(quantity),
        'departmentId':plan.planning_requirement.demand.department_id,'requiredDate':plan.required_date.isoformat()}
    return proof,material


def _identity(demand):
    q=ExternalIdentity.objects.filter(source_system=SYSTEM,source_object_type=ENTITY,target_entity_type='planning.Demand',target_entity_id=str(demand.pk))
    if q.count()!=1:
        fail('MATERIAL_DEMAND_PROOF_UNPROVEN','需求缺少唯一正式来源登记证明。')
    return q.get()


def verify_demand(demand, *, current=True, actor=None):
    identity=_identity(demand);meta=identity.audit_metadata
    if not isinstance(meta,dict) or not isinstance(meta.get('sourceProof'),dict):
        fail('MATERIAL_DEMAND_PROOF_UNPROVEN','正式来源登记关系的结构化证据缺失。')
    proof=meta['sourceProof']
    event=OrganizationOperatingAuditRecord.objects.filter(pk=meta.get('auditId'),action_code=CREATE,
        target_type='Demand',target_id=demand.pk,organization_id=identity.organization_id).first()
    request=MasterDataWriteRequest.objects.filter(pk=meta.get('writeRequestId'),status='COMMITTED',organization_id=identity.organization_id,
        action_code=CREATE,entity_type=ENTITY).first()
    if not (identity.mapping_status==ExternalIdentity.MappingStatus.MATCH and identity.source_fingerprint==_canonical_hash(proof)
            and event and event.after_snapshot.get('sourceProof')==proof and event.after_snapshot.get('authorization',{}).get('allowed')
            and request and request.result.get('demandId')==demand.pk and request.result.get('auditId')==event.pk
            and isinstance(request.audit_metadata,dict)
            and request.request_hash==_canonical_hash(request.audit_metadata)
            and request.audit_metadata.get('expectedSourceFingerprint')==identity.source_fingerprint
            and demand.source_type==SOURCE and demand.source_document_type==proof.get('sourceObjectType')
            and demand.source_document_id==str(proof.get('sourceLineId')) and demand.source_document_no==proof.get('sourceDocumentNo')
            and demand.material_id==proof.get('materialId') and _fact_quantity_equals(proof.get('requiredQty'),demand.required_qty)
            and demand.department_id==proof.get('departmentId') and demand.required_date.isoformat()==proof.get('requiredDate')):
        fail('MATERIAL_DEMAND_PROOF_UNPROVEN','原需求、来源、审计或同次动作证明不一致。')
    if not BusinessStateTransition.objects.filter(object_type='Demand',object_id=demand.pk,source_state='',target_state='draft',audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}').exists():
        fail('MATERIAL_DEMAND_PROOF_UNPROVEN','登记缺少原统一状态初始化事实。')
    if demand.status=='confirmed':
        confirmations=list(BusinessStateTransition.objects.filter(object_type='Demand',object_id=demand.pk,
            source_state='draft',target_state='confirmed',action_code=CONFIRM))
        if len(confirmations)!=1 or not OrganizationOperatingAuditRecord.objects.filter(pk=_audit_id(confirmations[0].audit_reference),
                action_code=CONFIRM,target_type='Demand',target_id=demand.pk,organization_id=identity.organization_id,
                after_snapshot__sourceFingerprint=identity.source_fingerprint,after_snapshot__authorization__allowed=True).exists():
            fail('MATERIAL_DEMAND_PROOF_UNPROVEN','需求确认缺少准确版本、资格及统一状态审计。')
    if current:
        _,plan,_=actor_plan(actor,proof['productionPlanId'],'planning.view')
        now,_=resolve_source(actor=actor,plan=plan,selection=proof)
        if _canonical_hash(now)!=identity.source_fingerprint:
            fail('MATERIAL_SOURCE_CHANGED','准确来源、版本、生产范围或数量依据已变化，原记录保留并待正式更正。')
    return proof,meta


def _overlap(actor, proof, *, lock=True):
    identities=ExternalIdentity.objects.filter(organization_id=actor.company_id,source_system=SYSTEM,source_object_type=ENTITY)
    if lock:
        identities=identities.select_for_update()
    for identity in identities:
        previous=(identity.audit_metadata or {}).get('sourceProof',{})
        if previous.get('salesOrderItemId')!=proof['salesOrderItemId']:
            continue
        if decimal(proof['rangeStart'],zero=True)<decimal(previous.get('rangeEnd')) and decimal(previous.get('rangeStart'),zero=True)<decimal(proof['rangeEnd']):
            if previous.get('bomVersionId')!=proof['bomVersionId'] or previous.get('manufacturingOutputId')!=proof['manufacturingOutputId']:
                fail('MATERIAL_SOURCE_CORRECTION_REQUIRED','重叠生产范围已有旧版本需求，须先核定正式更正，不得新版再次计量。')
            if not set(previous.get('sourceAtoms',[]))&set(proof['sourceAtoms']):continue
            demand=Demand.objects.get(pk=identity.target_entity_id)
            verify_demand(demand,current=False)
            if _canonical_hash(previous)==_canonical_hash(proof):return demand,identity.audit_metadata['auditId']
            fail('MATERIAL_DEMAND_RANGE_OVERLAP','同一原生材料来源已有有效需求覆盖本生产范围；不能因请求键、BOM别名或版本变化重复登记。')
    return None,None


def _registration_basis(*,actor,plan,selection,expected_fingerprint=SOURCE_EXPECTATION_UNSET,lock=False,resolved=None):
    """Same native source, quantity, version and overlap checks for read/write."""
    proof,material=resolved if resolved is not None else resolve_source(actor=actor,plan=plan,selection=selection)
    if expected_fingerprint is not SOURCE_EXPECTATION_UNSET and _canonical_hash(proof)!=expected_fingerprint:
        fail('MATERIAL_SOURCE_CHANGED','来源事实已变化，请重新读取，不能使用旧确认依据。')
    existing,audit_id=_overlap(actor,proof,lock=lock)
    return proof,material,existing,audit_id


def _confirmation_basis(*,demand,actor,proof,expected_fingerprint=SOURCE_EXPECTATION_UNSET):
    """Authorization is always actor_plan(CONFIRM), never CREATE or canPlan."""
    verify_demand(demand,current=True,actor=actor)
    if expected_fingerprint is not SOURCE_EXPECTATION_UNSET and expected_fingerprint!=_canonical_hash(proof):
        fail('MATERIAL_SOURCE_CHANGED','确认来源版本与原登记不一致。')
    if demand.status not in {'draft','confirmed'}:
        fail('MATERIAL_DEMAND_STATE_CONFLICT','当前需求状态不允许确认。')


def _action_projection(action,callback):
    from pde.product_design_service import ProductDesignError
    from sales.manufacturing_input import ManufacturingInputError
    code=CREATE if action=='register' else CONFIRM
    base={'actionCode':code,'requiredPermission':code,'allowed':False,'currentStateSource':'server'}
    try:
        outcome=callback()
        return {**base,**outcome}
    except (PlanningBusinessError,ProductDesignError,ManufacturingInputError) as error:
        status=getattr(error,'http_status',409)
        if status>=500:
            raise
        pending={'MATERIAL_SOURCE_CHANGED','MATERIAL_DEMAND_PROOF_UNPROVEN','MATERIAL_PRODUCTION_SCOPE_UNPROVEN',
            'MATERIAL_SOURCE_RELATION_UNPROVEN','MATERIAL_SOURCE_QUANTITY_UNPROVEN','MATERIAL_ENGINEERING_NOT_RELEASED',
            'MATERIAL_QUANTITY_BASIS_MISSING','MATERIAL_SOURCE_UNIT_UNPROVEN','MATERIAL_SOURCE_NUMBER_UNPROVEN',
            'MATERIAL_SOURCE_CORRECTION_REQUIRED'}
        category='QUALIFICATION_MISSING' if status==403 else 'SOURCE_PENDING' if error.code in pending else 'CONDITION_NOT_MET'
        return {**base,'reason':getattr(error,'message',str(error)),'reasonCode':error.code,'reasonCategory':category,
            'writeRejectionStatus':status,'sourceStatus':'PENDING_REVALIDATION' if category=='SOURCE_PENDING' else 'NOT_REVALIDATED'}


def _register_projection(user,plan,selection,*,expected_fingerprint=SOURCE_EXPECTATION_UNSET,resolved=None):
    def validate():
        actor,authorized_plan,_=actor_plan(user,plan.pk,CREATE)
        proof,_,existing,_=_registration_basis(actor=actor,plan=authorized_plan,selection=selection,
            expected_fingerprint=expected_fingerprint,resolved=resolved)
        return {'allowed':existing is None,'reason':'当前准确来源及范围可登记，提交时重新核验。' if existing is None else '本来源范围已登记，不再新增；可回查原需求。',
            'reasonCode':None if existing is None else 'MATERIAL_DEMAND_ALREADY_REGISTERED','reasonCategory':'READY' if existing is None else 'ALREADY_RECORDED',
            'productionPlanId':plan.pk,'existingDemandId':existing.pk if existing else None,'sourceFingerprint':_canonical_hash(proof),
            'sourceStatus':'CURRENT','repeatOutcome':'HISTORICAL_RECEIPT_ONLY' if existing else None}
    return _action_projection('register',validate)


@transaction.atomic
def action_context(*,user,demand_id,selection=None,expected_fingerprint=SOURCE_EXPECTATION_UNSET):
    if type(demand_id) is not int or demand_id<=0:
        fail('MATERIAL_DEMAND_INPUT_INVALID','须准确选择已有正式用料需求。',400)
    demand=Demand.objects.select_related('department').filter(pk=demand_id,source_type=SOURCE,department__company_id=getattr(user,'company_id',None)).first()
    if not demand:
        fail('MATERIAL_DEMAND_NOT_FOUND','本范围内未找到原正式生产用料需求。',404)
    proof,_=verify_demand(demand,current=False)
    actor,plan,_=actor_plan(user,proof['productionPlanId'],'planning.view')
    # Optional original selection is an identity assertion, never another source.
    if selection:
        for field in ['productionPlanId','sourceObjectType','sourceLineId','rangeStart','rangeEnd']:
            if field not in selection:
                continue
            same=decimal(selection[field],zero=True)==decimal(proof[field],zero=True) if field in {'rangeStart','rangeEnd'} else selection[field]==proof[field]
            if not same:
                fail('MATERIAL_DEMAND_CONTEXT_MISMATCH','所选需求、生产计划、来源明细或范围不一致，请重新选择准确对象。')
    def confirmation():
        authorized,_,_=actor_plan(actor,plan.pk,CONFIRM)
        _confirmation_basis(demand=demand,actor=authorized,proof=proof,expected_fingerprint=expected_fingerprint)
        done=demand.status=='confirmed'
        return {'allowed':not done,'reason':'该准确需求当前可确认，提交时重新核验。' if not done else '本需求已确认，无需重复办理。',
            'reasonCode':'MATERIAL_DEMAND_ALREADY_CONFIRMED' if done else None,'reasonCategory':'ALREADY_RECORDED' if done else 'READY',
            'demandId':demand.pk,'productionPlanId':plan.pk,'sourceFingerprint':_canonical_hash(proof),'sourceStatus':'CURRENT',
            'repeatOutcome':'HISTORICAL_RECEIPT_ONLY' if done else None}
    confirmed=_action_projection('confirm',confirmation)
    registered=_register_projection(actor,plan,proof,expected_fingerprint=expected_fingerprint)
    return {'sourceProof':proof,'sourceFingerprint':_canonical_hash(proof),'fingerprintBasis':'REGISTERED_SOURCE_VERSION',
        'demandId':demand.pk,'demandNo':demand.demand_no,'statusLabel':demand.get_status_display(),
        'currentSourceStatus':confirmed['sourceStatus'],'actionAuthorization':{'register':registered,'confirm':confirmed},
        'businessWriteCount':0,'materialReadiness':'NOT_ASSESSED','materialReadinessLabel':'需求资格不代表原料已占用、备齐或领用'}


@transaction.atomic
def register(*,user,payload,key):
    allowed={'productionPlanId','sourceObjectType','sourceLineId','rangeStart','rangeEnd','expectedSourceFingerprint','reason'}
    if not isinstance(payload,dict) or set(payload)!=allowed or not str(payload.get('reason') or '').strip():
        fail('MATERIAL_DEMAND_INPUT_INVALID','必须选择准确来源、范围、来源指纹及登记理由，不接收客户端物料/单位/数量/身份/状态。',400)
    _intent(payload,key)
    actor,plan,decision=actor_plan(user,payload['productionPlanId'],CREATE,lock=True)
    request,created,_=_write_request(user=actor,action_code=CREATE,entity_type=ENTITY,key=key,request_body=payload)
    if not created and request.status=='COMMITTED':return _own_receipt(request,actor)
    proof,material,existing,audit_id=_registration_basis(actor=actor,plan=plan,selection=payload,
        expected_fingerprint=payload['expectedSourceFingerprint'],lock=True)
    if existing:
        # Different request keys must not create even an extra action record.
        original=_identity(existing);old_proof=original.audit_metadata['sourceProof']
        transaction.set_rollback(True)
        return {'demandId':existing.pk,'auditId':audit_id,'sourceIdentityId':original.pk,
            'sourceFingerprint':original.source_fingerprint,'requiredQty':existing.quantity_text,
            'uomId':old_proof['uomId'],'uomCode':old_proof['uomCode'],'idempotent':True,'duplicateSource':True,'historicalReceiptOnly':True}
    demand=create_business_object_with_initial_state(model=Demand,initial_state='draft',demand_no=f'PMD-{request.pk}',
        source_type=SOURCE,source_document_type=proof['sourceObjectType'],source_document_id=str(proof['sourceLineId']),
        source_document_no=proof['sourceDocumentNo'],material=material,required_qty=Decimal(proof['requiredQty']).quantize(Decimal('.000001')),required_date=plan.required_date,
        department=plan.planning_requirement.demand.department,reason=payload['reason'],created_by=actor)
    demand.demand_no=_number('DM',demand);demand.full_clean();demand.save(update_fields=['demand_no'])
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,action_code=CREATE,
        target_type='Demand',target_id=demand.pk,target_label=demand.demand_no,reason=payload['reason'],
        after_snapshot={'sourceProof':proof,'sourceFingerprint':_canonical_hash(proof),'authorization':decision,'state':'draft'})
    identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system=SYSTEM,source_type=CONTRACT,
        source_object_type=ENTITY,external_id=_canonical_hash({'atoms':sorted(proof['sourceAtoms']),'range':[proof['rangeStart'],proof['rangeEnd']],'orderItem':proof['salesOrderItemId']}),
        target_entity_type='planning.Demand',target_entity_id=str(demand.pk),mapping_status=ExternalIdentity.MappingStatus.MATCH,
        source_fingerprint=_canonical_hash(proof),audit_metadata={'sourceProof':proof,'auditId':event.pk,'writeRequestId':request.pk})
    record_projected_business_transition(object_type='Demand',object_id=demand.pk,source_state='',target_state='draft',
        action_code=CREATE,operator=actor,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('','draft')})
    result={'demandId':demand.pk,'auditId':event.pk,'sourceIdentityId':identity.pk,'sourceFingerprint':identity.source_fingerprint,
        'requiredQty':demand.quantity_text,'uomId':proof['uomId'],'uomCode':proof['uomCode'],'idempotent':False}
    _commit_request(request,result);return result


@transaction.atomic
def confirm(*,user,payload,key):
    if not isinstance(payload,dict) or set(payload)!={'demandId','expectedSourceFingerprint','reason'} or type(payload['demandId']) is not int or not str(payload['reason']).strip():
        fail('MATERIAL_DEMAND_INPUT_INVALID','确认须明确原需求、来源指纹及理由，不接受指定状态。',400)
    _intent(payload,key)
    demand=Demand.objects.select_for_update().select_related('department').filter(pk=payload['demandId'],source_type=SOURCE,department__company_id=getattr(user,'company_id',None)).first()
    if not demand:fail('MATERIAL_DEMAND_NOT_FOUND','本范围内未找到原正式生产用料需求。',404)
    proof,meta=verify_demand(demand,current=False)
    actor,plan,decision=actor_plan(user,proof['productionPlanId'],CONFIRM,lock=True)
    request,created,_=_write_request(user=actor,action_code=CONFIRM,entity_type=ENTITY,key=key,request_body=payload)
    if not created and request.status=='COMMITTED':return _own_receipt(request,actor)
    _confirmation_basis(demand=demand,actor=actor,proof=proof,expected_fingerprint=payload['expectedSourceFingerprint'])
    if demand.status=='confirmed':
        transaction.set_rollback(True);return {'demandId':demand.pk,'sourceFingerprint':_canonical_hash(proof),
            'requiredQty':demand.quantity_text,'uomId':proof['uomId'],'uomCode':proof['uomCode'],
            'idempotent':True,'duplicateSource':True,'historicalReceiptOnly':True}
    if demand.status!='draft':fail('MATERIAL_DEMAND_STATE_CONFLICT','当前需求状态不允许确认。')
    event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,action_code=CONFIRM,
        target_type='Demand',target_id=demand.pk,target_label=demand.demand_no,reason=payload['reason'],
        before_snapshot={'state':'draft'},after_snapshot={'state':'confirmed','sourceIdentityId':_identity(demand).pk,'sourceFingerprint':_canonical_hash(proof),'authorization':decision})
    transition_business_object(business_object=demand,object_type='Demand',source_state='draft',target_state='confirmed',
        action_code=CONFIRM,operator=actor,reason=payload['reason'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',
        allowed_transitions={('draft','confirmed')},version_field=None)
    result={'demandId':demand.pk,'auditId':event.pk,'sourceFingerprint':_canonical_hash(proof),
        'requiredQty':demand.quantity_text,'uomId':proof['uomId'],'uomCode':proof['uomCode'],'idempotent':False}
    _commit_request(request,result);return result


@transaction.atomic
def preview(*,user,selection,expected_fingerprint=SOURCE_EXPECTATION_UNSET):
    actor,plan,_=actor_plan(user,selection.get('productionPlanId'),'planning.view')
    proof,material=resolve_source(actor=actor,plan=plan,selection=selection)
    registered=_register_projection(actor,plan,selection,expected_fingerprint=expected_fingerprint,resolved=(proof,material))
    return {'sourceProof':proof,'sourceFingerprint':_canonical_hash(proof),'actionAuthorization':{'register':registered,
        'confirm':{'actionCode':CONFIRM,'requiredPermission':CONFIRM,'allowed':False,'reason':'须明确选择已登记的准确需求，来源预览不授予确认资格。',
            'reasonCode':'MATERIAL_DEMAND_OBJECT_REQUIRED','reasonCategory':'OBJECT_REQUIRED','currentStateSource':'server'}},
        'currentSourceStatus':'CURRENT','businessWriteCount':0,'materialReadiness':'NOT_ASSESSED','materialReadinessLabel':'原料占用及备料证明待核'}


@transaction.atomic
def source_scope(*,user,plan_id):
    """Read the original approved range before the caller selects a subrange."""
    _,plan,_=actor_plan(user,plan_id,'planning.view')
    item,start,end,audit_id=_approved_scope(plan)
    return {'contractVersion':'PCE-PRODUCTION-MATERIAL-SOURCE-CATALOGUE-V1','factSource':'server',
        'readMode':'APPROVED_RANGE_CONTEXT','productionPlanId':plan.pk,'productionPlanNo':plan.plan_no,
        'approvedRangeStart':str(start),'approvedRangeEnd':str(end),'productionUomId':item.uom_id,
        'productionUomCode':item.uom.code,'productionDecimalPlaces':item.uom.decimal_places,
        'planConfirmationAuditId':audit_id,'candidates':None,'candidateCount':None,
        'factLoadStatus':'loaded','statusLabel':'已读取原批准生产范围，请明确选择本次范围后读取来源',
        'businessWriteCount':0}


@transaction.atomic
def source_candidates(*,user,plan_id,range_start,range_end):
    """Read the approved plan's exact published BOM rows before any Demand exists.

    BOM aggregates and their distinct engineering details are alternative source
    scopes, never additive quantities. Single-contribution aliases collapse to
    the BOM row. Original source atoms remain the registration overlap gate.
    No quantity formula, action permission or registration decision lives here.
    """
    from pde.models import BOMItem,BOMItemSourceRequirement
    from pde.product_design_service import ProductDesignError
    from sales.manufacturing_input import ManufacturingInputError
    actor,plan,_=actor_plan(user,plan_id,'planning.view')
    context=_production_source_context(plan=plan,selection={'rangeStart':range_start,'rangeEnd':range_end},require_line=False)
    item,approved_start,approved_end,_,start,end,_,output,version=context
    rows=BOMItem.objects.select_related('material','uom').filter(bom_version=version,item_role='material').order_by('line_no','pk')
    candidates=[];seen=set();coverage={}
    def project(row,source_type,line_id,line_no,document_no,coverage_kind,links):
        if row.material.company_id!=actor.company_id or row.uom.company_id!=actor.company_id:
            fail('MATERIAL_SOURCE_RELATION_UNPROVEN','本发布版本含归属未获证明的材料或单位，来源目录待核。')
        identity=(source_type,line_id)
        if identity in seen:
            return
        seen.add(identity)
        selection={'productionPlanId':plan.pk,'sourceObjectType':source_type,'sourceLineId':line_id,
            'rangeStart':str(start),'rangeEnd':str(end)}
        entry={'candidateKey':source_type+':'+str(line_id),'sourceObjectType':source_type,
            'sourceTypeLabel':'正式BOM材料明细' if source_type=='BOMItem' else '正式工程材料需求明细','sourceLineId':line_id,
            'sourceLineNo':line_no,'sourceDocumentNo':document_no,'bomLineNo':row.line_no,
            'coverageKind':coverage_kind,'coverageGroup':'BOMItem:'+str(row.pk),
            'coverageMeaningLabel':'BOM整组与其工程明细是重叠的备选来源，不可重复叠加；登记仍按原来源关系防重',
            'sourceVersion':version.bom_version,'sourceRevision':version.revision,'bomVersionId':version.pk,
            'materialId':row.material_id,'materialCode':row.material.code,'materialName':row.material.name,
            'uomId':row.uom_id,'uomCode':row.uom.code,'requiredQty':None,'quantityBasis':None,
            'selection':selection,'expectedSourceFingerprint':None,'sourceDetails':None,
            'sourceAtoms':None,'sourceAliases':[],
            'existingDemandId':None,'existingDemandNo':None,'qualificationPreviewRequired':True,'selectableForPreview':False}
        try:
            proof,_=resolve_source(actor=actor,plan=plan,selection=selection,_resolved_context=context)
            if proof['bomItemId']!=row.pk:
                proven_row=BOMItem.objects.get(pk=proof['bomItemId'],bom_version=version)
                links=list(BOMItemSourceRequirement.objects.select_related('material_requirement__calculation').filter(bom_item=proven_row).order_by('material_requirement__sequence','pk'))
                entry.update(bomLineNo=proven_row.line_no,coverageGroup='BOMItem:'+str(proven_row.pk),
                    materialId=proof['materialId'],materialCode=proof['materialCode'],materialName=proof['materialName'],uomId=proof['uomId'],uomCode=proof['uomCode'])
            existing,_=_overlap(actor,proof,lock=False)
            coverage_key=(tuple(sorted(proof['sourceAtoms'])),proof['requiredQty'],proof['uomId'])
            if coverage_key in coverage:
                coverage[coverage_key]['sourceAliases'].append({key:entry[key] for key in ['sourceObjectType','sourceLineId','sourceLineNo','sourceDocumentNo']})
                return
            details=[]
            for link in links:
                requirement=link.material_requirement
                details.append({'sourceObjectType':'EngineeringMaterialRequirement','sourceTypeLabel':'工程材料需求明细',
                    'sourceLineId':requirement.pk,'sourceLineNo':requirement.sequence,
                    'sourceDocumentNo':requirement.calculation.calculation_no,'calculationId':requirement.calculation_id,
                    'contributedNetQty':str(link.contributed_quantity),'sourceGrossQty':str(requirement.gross_quantity) if requirement.gross_quantity is not None else None,
                    'uomId':requirement.uom_id,'uomCode':proof['uomCode'],'quantityBasis':requirement.quantity_basis,
                    'quantityMeaningLabel':'原工程订单行总量与BOM净贡献证明，不是本次范围额外需求，不与requiredQty重复相加',
                    'selectedInThisRow':source_type=='BOMItem' or requirement.pk==line_id,
                    'selectableAlias':False,'meaningLabel':'来源贡献证明；需要逐明细选择时采用目录中该明细候选，不重复累计'})
            entry.update(requiredQty=proof['requiredQty'],quantityBasis=proof['quantityBasis'],sourceDetails=details,sourceAtoms=proof['sourceAtoms'],
                expectedSourceFingerprint=_canonical_hash(proof),sourceStatus='CURRENT',quantityStatus='PROVEN',selectableForPreview=True,
                statusLabel='已登记，可查看原需求' if existing else '来源已核定，选择后读取登记资格',
                reasonCode='MATERIAL_DEMAND_ALREADY_REGISTERED' if existing else None,
                reason='本来源范围已登记，不能重复新增。' if existing else '来源核定不是办理资格，选择后须读取原登记资格。',
                existingDemandId=existing.pk if existing else None,existingDemandNo=existing.demand_no if existing else None)
            coverage[coverage_key]=entry
        except (PlanningBusinessError,ProductDesignError,ManufacturingInputError) as error:
            if getattr(error,'http_status',409)>=500:
                raise
            entry.update(sourceStatus='PENDING_REVALIDATION',quantityStatus='UNKNOWN',statusLabel='来源或适用条件待核',
                reasonCode=error.code,reason=getattr(error,'message',str(error)),previewRejectionStatus=getattr(error,'http_status',409))
        candidates.append(entry)
    for row in rows:
        links=list(BOMItemSourceRequirement.objects.select_related('material_requirement__calculation').filter(bom_item=row).order_by('material_requirement__sequence','pk'))
        project(row,'BOMItem',row.pk,row.line_no,version.bom.bom_code if version.bom_id else None,
            'BOM_AGGREGATE' if len(links)>1 else 'BOM_ROW',links)
        if len(links)>1:
            for link in links:
                requirement=link.material_requirement
                if requirement.calculation.company_id!=actor.company_id:
                    continue  # Parent native resolver already exposes the controlled source failure, never foreign details.
                project(row,'EngineeringMaterialRequirement',requirement.pk,requirement.sequence,
                    requirement.calculation.calculation_no,'ENGINEERING_DETAIL',links)
    return {'contractVersion':'PCE-PRODUCTION-MATERIAL-SOURCE-CATALOGUE-V1','factSource':'server',
        'readMode':'SOURCE_CANDIDATES',
        'productionPlanId':plan.pk,'productionPlanNo':plan.plan_no,'rangeStart':str(start),'rangeEnd':str(end),
        'approvedRangeStart':str(approved_start),'approvedRangeEnd':str(approved_end),
        'productionUomId':item.uom_id,'productionUomCode':item.uom.code,'productionDecimalPlaces':item.uom.decimal_places,
        'manufacturingOutputId':output.pk,'bomVersionId':version.pk,'sourceVersion':version.bom_version,
        'candidates':candidates,'candidateCount':len(candidates),
        'factLoadStatus':'loaded' if candidates else 'empty_valid',
        'statusLabel':'已读取本计划范围正式用料来源' if candidates else '本准确发布版本没有原材料明细',
        'quantityMeaningLabel':'requiredQty为该候选所选范围的原权威需求量；BOM整组与工程明细不可叠加，同源别名不重复登记',
        'businessWriteCount':0,'registrationEligibilitySource':'GET原准确selection及expectedSourceFingerprint的actionAuthorization.register'}


def result_query(*,user,plan_id,key,action):
    permission=CREATE if action=='register' else CONFIRM if action=='confirm' else None
    if not permission or not key:fail('MATERIAL_RESULT_INPUT_INVALID','须提供同一次登记或确认的原动作键。',400)
    actor,plan,_=actor_plan(user,plan_id,permission)
    row=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,action_code=permission,entity_type=ENTITY,idempotency_key=key).first()
    if row and row.status=='COMMITTED':
        demand=Demand.objects.filter(pk=row.result.get('demandId'),department__company_id=actor.company_id,source_type=SOURCE).first()
        if not demand or _identity(demand).audit_metadata['sourceProof'].get('productionPlanId')!=plan.pk:
            fail('MATERIAL_RESULT_NOT_FOUND','原动作不属于本生产范围。',404)
        _own_receipt(row,actor)
    return {'resultState':'COMMITTED' if row and row.status=='COMMITTED' else 'UNKNOWN','sameActionKey':key,
        'result':row.result if row and row.status=='COMMITTED' else None,'automaticReplayAllowed':False,'historicalReceiptOnly':True,'businessWriteCount':0}


def source_fields(demand):
    if demand.source_type!=SOURCE:return {}
    proof,meta=verify_demand(demand,current=False)
    return {'productionMaterialSource':{**proof,'sourceFingerprint':_canonical_hash(proof),'registrationAuditId':meta['auditId'],
            'currentSourceStatus':'NOT_REVALIDATED','materialReadiness':'NOT_ASSESSED'},
        'uomId':proof['uomId'],'uomCode':proof['uomCode'],'materialReadinessLabel':'需求已登记不表示原料已占用、备齐或领用'}
