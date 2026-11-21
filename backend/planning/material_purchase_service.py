"""Demand-scoped approved BUY evidence on the original supply arrangement chain.

Approval ingestion is an internal controlled-maintenance operation, never a
client assertion or a public self-approval action. Quantity remains a separate
explicit planner input; unknown inventory is never deducted or recorded as zero.
"""
from decimal import Decimal, InvalidOperation
from threading import RLock
from django.db import transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord, User
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from workflow_runtime.state_transitions import create_business_object_with_initial_state, record_projected_business_transition, transition_business_object
from .models import Demand, PlanningRequirement
from . import material_demand_service as native
from .services import PlanningBusinessError

SYSTEM = 'PCE_PRODUCTION_MATERIAL_PURCHASE_APPROVAL'
ENTITY = 'ProductionMaterialPurchaseApproval'
PERMISSION = 'planning.purchase_plan.confirm'
LOCK = RLock()


def fail(code, message, status=409):
    raise PlanningBusinessError(code, message, http_status=status)


def scoped_demand(user, demand_id, permission='planning.view', lock=False):
    rows = Demand.objects.select_related('department', 'material')
    if lock:
        rows = rows.select_for_update()
    demand = rows.filter(pk=demand_id, source_type=native.SOURCE, department__company_id=getattr(user, 'company_id', None)).first()
    if not demand:
        fail('MATERIAL_PURCHASE_DEMAND_NOT_FOUND', '本范围内没有准确的正式用料需求。', 404)
    proof, _ = native.verify_demand(demand, current=False)
    actor, _, decision = native.actor_plan(user, proof['productionPlanId'], permission, lock=lock)
    native.verify_demand(demand, current=True, actor=actor)
    if demand.status != 'confirmed':
        fail('MATERIAL_PURCHASE_DEMAND_UNCONFIRMED', '须先按原资格确认准确需求。')
    return actor, demand, proof, decision


def approved_source(demand, actor=None):
    proof, _ = native.verify_demand(demand, current=False)
    matches = ExternalIdentity.objects.filter(organization_id=demand.department.company_id,
        source_system=SYSTEM, source_object_type=ENTITY,
        target_entity_type='planning.Demand', target_entity_id=str(demand.pk))
    if matches.count() != 1:
        fail('MATERIAL_PURCHASE_APPROVAL_REQUIRED', '本需求尚无准确来源、版本及批准范围的外购批准，不能借用其他订单裁决。')
    identity = matches.get()
    facts = identity.audit_metadata
    basis = facts.get('approval') if isinstance(facts, dict) else None
    if not isinstance(basis, dict):
        fail('MATERIAL_PURCHASE_APPROVAL_UNPROVEN', '外购批准的结构化依据未核实。')
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=facts.get('auditId'),
        action_code=PERMISSION, organization_id=identity.organization_id,
        target_type=ENTITY, target_id=demand.pk).first()
    request = MasterDataWriteRequest.objects.filter(pk=facts.get('writeRequestId'),
        entity_type=ENTITY, action_code=PERMISSION, organization_id=identity.organization_id,
        status='COMMITTED').first()
    expected = {'companyId':demand.department.company_id, 'demandId':demand.pk,
        'demandNo':demand.demand_no, 'sourceProof':proof, 'sourceFingerprint':_canonical_hash(proof), 'branch':'BUY'}
    if (any(basis.get(k) != v for k,v in expected.items())
        or identity.mapping_status != 'MATCH' or identity.source_fingerprint != _canonical_hash(basis)
        or not basis.get('approvalReference') or not basis.get('approvalEvidenceSHA256')
        or not audit or audit.after_snapshot.get('approval') != basis
        or not audit.after_snapshot.get('authorization',{}).get('allowed')
        or not request or request.request_hash != _canonical_hash(request.audit_metadata)
        or request.audit_metadata.get('approval') != basis
        or request.result.get('auditId') != audit.pk or request.result.get('identityId') != identity.pk):
        fail('MATERIAL_PURCHASE_APPROVAL_UNPROVEN', '外购批准与准确需求、来源、版本、范围或原审计不一致。')
    verifier = actor or User.objects.filter(pk=audit.actor_id, is_active=True).first()
    if not verifier:
        fail('MATERIAL_PURCHASE_SOURCE_CURRENT_UNPROVEN', '来源当前核定所需的原业务身份未取得。')
    native.verify_demand(demand, current=True, actor=verifier)
    return {'identityId':identity.pk, 'auditId':audit.pk, 'fingerprint':identity.source_fingerprint,
        'approval':basis, 'statusLabel':'本需求准确来源及范围已批准外购'}


def ingest_approved_purchase(*, user, demand_id, approval_reference, approval_evidence_sha256, key):
    """Called only by the approved maintenance receipt, not exposed as HTTP POST."""
    with LOCK, transaction.atomic():
        actor, demand, proof, decision = scoped_demand(user, demand_id, PERMISSION, lock=True)
        if not isinstance(approval_reference,str) or not approval_reference.strip() or not isinstance(approval_evidence_sha256,str) or len(approval_evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in approval_evidence_sha256):
            fail('MATERIAL_PURCHASE_APPROVAL_INPUT_REQUIRED', '须归档已批准业务裁决的原文引用及准确SHA256。', 400)
        basis={'companyId':actor.company_id,'demandId':demand.pk,'demandNo':demand.demand_no,
            'sourceProof':proof,'sourceFingerprint':_canonical_hash(proof),'branch':'BUY',
            'approvalReference':approval_reference.strip(),'approvalEvidenceSHA256':approval_evidence_sha256}
        old=ExternalIdentity.objects.filter(organization_id=actor.company_id,source_system=SYSTEM,
            source_object_type=ENTITY,target_entity_type='planning.Demand',target_entity_id=str(demand.pk)).first()
        if old:
            current=approved_source(demand,actor)
            if current['approval']!=basis:
                fail('MATERIAL_PURCHASE_APPROVAL_CONFLICT','原外购批准保留，不能静默覆盖准确依据。')
            return {**current,'idempotent':True,'businessWriteCount':0}
        body={'approval':basis,'actorId':actor.pk}
        request,created,_=_write_request(user=actor,action_code=PERMISSION,entity_type=ENTITY,key=key,request_body=body)
        if not created:
            fail('MATERIAL_PURCHASE_APPROVAL_RESULT_PENDING','请查询原同次结果，不重放维护写入。')
        event=OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,
            action_code=PERMISSION,target_type=ENTITY,target_id=demand.pk,target_label=demand.demand_no,
            reason=approval_reference,after_snapshot={'approval':basis,'authorization':decision,'maintenanceOnly':True,'purchaseQuantityConfirmed':False})
        identity=ExternalIdentity.objects.create(organization_id=actor.company_id,source_system=SYSTEM,
            source_type='APPROVED_BUSINESS_DECISION',source_object_type=ENTITY,
            external_id=_canonical_hash({'demandId':demand.pk,'sourceFingerprint':_canonical_hash(proof)}),
            target_entity_type='planning.Demand',target_entity_id=str(demand.pk),mapping_status='MATCH',
            source_fingerprint=_canonical_hash(basis),audit_metadata={'approval':basis,'auditId':event.pk,'writeRequestId':request.pk})
        result={'demandId':demand.pk,'identityId':identity.pk,'auditId':event.pk,'idempotent':False}
        _commit_request(request,result)
        return result


def context(*,user,demand_id):
    actor,demand,proof,_=scoped_demand(user,demand_id)
    try:
        approval=approved_source(demand,actor);allowed=True;reason='须由原计划岗明确实际采购数量、单位及依据；库存未核定，不自动抵减。'
        code='MATERIAL_PURCHASE_QUANTITY_REQUIRED'
    except PlanningBusinessError as error:
        if error.code!='MATERIAL_PURCHASE_APPROVAL_REQUIRED':raise
        approval=None;allowed=False;reason=error.message;code=error.code
    existing=PlanningRequirement.objects.filter(demand=demand).first()
    if existing:
        validate_arrangement(existing)
        code=None;reason='已读取计划岗明确登记的采购数量及原依据，提交仍重核当前资格。'
    return {'demandId':demand.pk,'demandNo':demand.demand_no,'requiredQty':demand.quantity_text,
        'uomId':proof['uomId'],'uomCode':proof['uomCode'],'sourceFingerprint':_canonical_hash(proof),
        'sourceProof':proof,'purchaseApproval':approval,'sourceAdmitted':allowed,
        'actualPurchaseQty':str(existing.net_required_qty) if existing else None,
        'requirementId':existing.pk if existing else None,
        'stockAvailableQty':None,'stockAvailabilityStatus':'UNKNOWN','reasonCode':code,'reason':reason,
        'quantityConfirmationRequired':existing is None,'businessWriteCount':0}


def result_query(*,user,demand_id,key):
    demand=Demand.objects.filter(pk=demand_id,source_type=native.SOURCE,department__company_id=getattr(user,'company_id',None)).first()
    if not demand:fail('MATERIAL_PURCHASE_RESULT_NOT_FOUND','本范围没有该同次结果。',404)
    proof,_=native.verify_demand(demand,current=False)
    actor,_,_=native.actor_plan(user,proof['productionPlanId'],'planning.view')
    request=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,
        entity_type='ProductionMaterialPurchaseArrangement',action_code='planning.requirement.calculate',idempotency_key=key).first()
    if not request or request.audit_metadata.get('actorId')!=actor.pk or request.audit_metadata.get('demandId')!=demand.pk:
        fail('MATERIAL_PURCHASE_RESULT_NOT_FOUND','未找到本办理人的准确同次结果。',404)
    if request.status!='COMMITTED':fail('MATERIAL_PURCHASE_RESULT_PENDING','同次结果尚未确认，不自动重放写入。')
    event=OrganizationOperatingAuditRecord.objects.filter(pk=request.result.get('auditId'),actor=actor,
        organization_id=actor.company_id,target_type='PlanningRequirement',action_code='planning.requirement.calculate').first()
    if not event or event.after_snapshot.get('state',{}).get('demandId')!=demand.pk:
        fail('MATERIAL_PURCHASE_RESULT_UNPROVEN','原同次结果与审计未核实。')
    return {**request.result,'historicalReceiptOnly':True,'currentEligibilityGranted':False,'businessWriteCount':0}


def prepare_requirement(*,user,demand_id,payload):
    """Original calculate entrance, explicit arrangement instead of stock deduction."""
    with LOCK,transaction.atomic():
        actor,demand,proof,decision=scoped_demand(user,demand_id,'planning.requirement.calculate',lock=True)
        approval=approved_source(demand,actor)
        required={'actualPurchaseQty','uomId','quantityBasis','expectedSourceFingerprint','expectedApprovalFingerprint','idempotencyKey'}
        if not isinstance(payload,dict) or set(payload)!=required:
            fail('MATERIAL_PURCHASE_QUANTITY_REQUIRED','本需求已获准外购；请由计划岗明确实际采购数量、原单位及依据，不能自动把工程净需求当采购量。',400)
        if payload['expectedSourceFingerprint']!=_canonical_hash(proof) or payload['expectedApprovalFingerprint']!=approval['fingerprint']:
            fail('MATERIAL_PURCHASE_SOURCE_CHANGED','来源或批准版本已变化，请重读准确上下文。')
        if type(payload['uomId']) is not int or payload['uomId']!=proof['uomId']:
            fail('MATERIAL_PURCHASE_UNIT_UNPROVEN','本包仅沿用准确来源单位，未取得其他采购单位换算依据。')
        raw=payload['actualPurchaseQty']
        if not isinstance(raw,str) or not isinstance(payload['quantityBasis'],str) or not payload['quantityBasis'].strip() or len(payload['quantityBasis'])>300:
            fail('MATERIAL_PURCHASE_QUANTITY_REQUIRED','须提供准确十进制字符串及实际采购数量依据。',400)
        try:
            qty=Decimal(raw)
            if not qty.is_finite() or qty<=0 or qty>=Decimal('1e14') or qty!=qty.quantize(Decimal('.000001')) or qty!=qty.quantize(Decimal(1).scaleb(-demand.material.base_uom.decimal_places)):raise ValueError()
        except (InvalidOperation,ValueError,KeyError):
            fail('MATERIAL_PURCHASE_QUANTITY_INVALID','实际采购数量超出原单位精度或准确容量；不得舍入。',400)
        body={'demandId':demand.pk,'approvalFingerprint':approval['fingerprint'],'sourceFingerprint':_canonical_hash(proof),'quantity':format(qty,'f'),'uomId':proof['uomId'],'quantityBasis':payload['quantityBasis'],'actorId':actor.pk}
        existing=PlanningRequirement.objects.select_for_update().filter(demand=demand).first()
        if existing:
            if existing.calculation_facts.get('purchaseArrangement')!=body:
                fail('MATERIAL_PURCHASE_ARRANGEMENT_CONFLICT','原供应安排已保存，数量或依据变化须沿正式更正规则办理。')
            return existing,None
        request,created,_=_write_request(user=actor,action_code='planning.requirement.calculate',entity_type='ProductionMaterialPurchaseArrangement',key=payload['idempotencyKey'],request_body=body)
        if not created:fail('MATERIAL_PURCHASE_RESULT_PENDING','请查询原同次动作结果。')
        row=create_business_object_with_initial_state(model=PlanningRequirement,initial_state='draft',
            requirement_no=f'TMP-PMR-{request.pk}',demand=demand,material=demand.material,
            demand_qty=demand.required_qty,available_qty=None,net_required_qty=qty,required_date=demand.required_date,
            supply_type='purchase',calculation_facts={'purchaseArrangement':body,'stockAvailableQty':None,
                'inventorySemantic':'UNKNOWN_NOT_DEDUCTED','inventoryWriteCount':0,'quantityMeaning':'PLANNER_EXPLICIT_PURCHASE_QUANTITY_NOT_CALCULATED_SHORTAGE'},created_by=actor)
        from .services import _number,record_audit
        row.requirement_no=_number('REQ',row);row.full_clean();row.save(update_fields=['requirement_no'])
        first=record_audit(user=actor,action_code='planning.requirement.calculate',target=row,target_type='PlanningRequirement',target_no=row.requirement_no,before={'status':''},after={'status':'draft',**body},authorization=decision)
        record_projected_business_transition(object_type='PlanningRequirement',object_id=row.pk,source_state='',target_state='draft',action_code='planning.requirement.calculate',operator=actor,reason=payload['quantityBasis'],audit_reference=f'OrganizationOperatingAuditRecord:{first.pk}',allowed_transitions={('','draft')})
        event=record_audit(user=actor,action_code='planning.requirement.calculate',target=row,target_type='PlanningRequirement',target_no=row.requirement_no,before={'status':'draft'},after={'status':'calculated',**body},authorization=decision)
        transition_business_object(business_object=row,object_type='PlanningRequirement',source_state='draft',target_state='calculated',action_code='planning.requirement.calculate',operator=actor,reason=payload['quantityBasis'],audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('draft','calculated')},version_field=None)
        _commit_request(request,{'requirementId':row.pk,'demandId':demand.pk,'auditId':event.pk})
        return row,event


def validate_arrangement(requirement):
    demand=requirement.demand;approval=approved_source(demand)
    basis=requirement.calculation_facts.get('purchaseArrangement',{})
    if (basis.get('demandId')!=demand.pk or basis.get('approvalFingerprint')!=approval['fingerprint']
        or basis.get('sourceFingerprint')!=approval['approval']['sourceFingerprint']
        or basis.get('uomId')!=approval['approval']['sourceProof']['uomId']
        or Decimal(basis.get('quantity','NaN'))!=requirement.net_required_qty
        or requirement.demand_qty!=demand.required_qty or requirement.available_qty is not None
        or not basis.get('quantityBasis')):
        fail('MATERIAL_PURCHASE_ARRANGEMENT_UNPROVEN','供应安排数量、单位、批准版本或来源不一致，不能继续采购。')
    return approval


def confirm_purchase_plan(*,user,requirement):
    from .models import PurchasePlan
    from .services import _number,record_audit
    with LOCK,transaction.atomic():
        actor,_,_,decision=scoped_demand(user,requirement.demand_id,PERMISSION,lock=True)
        validate_arrangement(requirement)
        old=PurchasePlan.objects.filter(planning_requirement=requirement).first()
        if old:
            if old.net_required_qty!=requirement.net_required_qty or old.available_qty is not None:
                fail('MATERIAL_PURCHASE_PLAN_CONFLICT','原采购计划与准确供应安排不一致。')
            return old,None
        if requirement.status!='calculated':
            fail('MATERIAL_PURCHASE_PLAN_STATE_INVALID','当前供应安排状态不能确认采购计划。')
        plan=create_business_object_with_initial_state(model=PurchasePlan,initial_state='draft',
            plan_no=f'TMP-PPM-{requirement.pk}',planning_requirement=requirement,material=requirement.material,
            required_qty=requirement.demand_qty,available_qty=None,net_required_qty=requirement.net_required_qty,
            required_date=requirement.required_date,source_id=str(requirement.pk),planning_engine='DIRECT_V1',
            run_batch=f'DIRECT-{requirement.pk}',source_version='DIRECT-V1',confirmed_by=actor)
        plan.plan_no=_number('PP',plan);plan.full_clean();plan.save(update_fields=['plan_no'])
        facts={'planNo':plan.plan_no,'requirementId':requirement.pk,'quantity':str(plan.net_required_qty),
            'purchaseArrangement':requirement.calculation_facts['purchaseArrangement'],'stockAvailableQty':None}
        first=record_audit(user=actor,action_code=PERMISSION,target=plan,target_type='PurchasePlan',target_no=plan.plan_no,before={'status':''},after={**facts,'status':'draft'},authorization=decision)
        record_projected_business_transition(object_type='PurchasePlan',object_id=plan.pk,source_state='',target_state='draft',action_code=PERMISSION,operator=actor,reason='按准确供应安排初始化采购计划',audit_reference=f'OrganizationOperatingAuditRecord:{first.pk}',allowed_transitions={('','draft')})
        event=record_audit(user=actor,action_code=PERMISSION,target=plan,target_type='PurchasePlan',target_no=plan.plan_no,before={'status':'draft'},after={**facts,'status':'confirmed'},authorization=decision)
        transition_business_object(business_object=plan,object_type='PurchasePlan',source_state='draft',target_state='confirmed',action_code=PERMISSION,operator=actor,reason='明确采购数量及依据后确认原采购计划',audit_reference=f'OrganizationOperatingAuditRecord:{event.pk}',allowed_transitions={('draft','confirmed')},version_field=None)
        requirement_event=record_audit(user=actor,action_code=PERMISSION,target=requirement,target_type='PlanningRequirement',target_no=requirement.requirement_no,before={'status':'calculated'},after={**facts,'status':'confirmed'},authorization=decision)
        transition_business_object(business_object=requirement,object_type='PlanningRequirement',source_state='calculated',target_state='confirmed',action_code=PERMISSION,operator=actor,reason='原采购计划确认',audit_reference=f'OrganizationOperatingAuditRecord:{requirement_event.pk}',allowed_transitions={('calculated','confirmed')},version_field=None)
        return plan,event


def material_allowed(material,request_item=None,plan=None):
    if not material or not material.is_active:return False
    if material.is_purchased:return True
    if request_item is not None:
        if request_item.material_id!=material.pk:return False
        plan=request_item.purchase_request.source_purchase_plan
    if not plan or plan.material_id!=material.pk or plan.planning_requirement.demand.source_type!=native.SOURCE:return False
    validate_arrangement(plan.planning_requirement)
    if plan.net_required_qty!=plan.planning_requirement.net_required_qty:return False
    if request_item is not None:
        proof=approved_source(plan.planning_requirement.demand)['approval']['sourceProof']
        if request_item.quantity!=plan.net_required_qty or request_item.unit!=proof['uomCode']:
            return False
    return True


def purchasing_unit(request_item):
    material=request_item.material
    if material.is_purchased:
        return material.unit
    if material_allowed(material,request_item=request_item):
        return approved_source(request_item.purchase_request.source_purchase_plan.planning_requirement.demand)['approval']['sourceProof']['uomCode']
    return None
