

# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from django.utils import timezone

from . import work_order_execution_service as execution

from .work_order_execution_service import _hash

from . import work_order_workshop_receipt_service as receipts

from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt as Receipt

from .work_order_release_admission_service import _effective

def _date(value):
    return value.isoformat() if value is not None else None

def _current_snapshot(operation, workshop, *, effective_center=None):
    from pde.plan_step_context_service import _company
    order, center, process = operation.work_order, effective_center or operation.work_center, operation.operation
    def step_fact(step):
        return {'id': step.pk, 'routingVersionId': step.routing_version_id,
            'companyId': _company(step),
            'operationId': step.operation_id, 'workCenterId': step.work_center_id,
            'workshopId': step.workshop_id, 'isActive': step.is_active} if step else None
    return {
        'companyId': order.company_id, 'workOrderId': order.pk,
        'productionPlanId': order.production_plan_id, 'workOrderVersion': order.version,
        'workOrderSnapshotHash': order.snapshot_hash, 'operationId': operation.pk,
        'operationSnapshotHash': operation.snapshot_hash, 'formalOperationId': operation.operation_id,
        'rootStepId': operation.root_step_id, 'effectiveStepId': operation.effective_step_id,
        'rootRoutingVersionId': operation.root_routing_version_id,
        'effectiveRoutingVersionId': operation.effective_routing_version_id,
        'engineeringVersion': deepcopy(operation.source_snapshot.get('frozenStep', {}).get('engineeringVersion')),
        'rootStep': step_fact(operation.root_step), 'currentStep': step_fact(operation.effective_step),
        'workCenter': {'id': center.pk, 'companyId': center.company_id,
            'workshopId': center.workshop_id, 'departmentId': center.department_id,
            'isActive': center.is_active, 'effectiveFrom': _date(center.effective_from),
            'effectiveTo': _date(center.effective_to)} if center else None,
        'process': {'id': process.pk, 'companyId': process.company_id,
            'workshopId': process.workshop_id, 'workCenterId': process.work_center_id,
            'isActive': process.is_active, 'effectiveFrom': _date(process.effective_from),
            'effectiveTo': _date(process.effective_to)} if process else None,
        'workshop': {'id': workshop.pk, 'companyId': workshop.company_id,
            'departmentId': workshop.department_id, 'isActive': workshop.is_active} if workshop else None,
    }

def _original_memberships(order):
    """Verify the full original receipt and all of its immutable members."""
    operations, _ = execution._verify(order)
    by_id = {item.pk: item for item in operations}
    matches = {}
    seen = set()
    for receipt in Receipt.objects.filter(work_order=order).select_related('workshop').order_by('pk'):
        fact = receipts._receipt(receipt)
        from .operation_resource_selection_service import original_group_source
        frozen, supplement = original_group_source(receipt)
        if frozen is None:
            continue
        if (receipt.company_id != order.company_id or receipt.work_order_version != order.version
                or receipt.work_order_snapshot_hash != order.snapshot_hash
                or frozen.get('productionPlanId') != order.production_plan_id
                or frozen.get('workOrderNo') != order.no or frozen.get('quantity') != str(order.quantity)
                or frozen.get('uomId') != order.uom_id
                or frozen.get('uomCode') != order.source_snapshot.get('uomCode')
                or frozen.get('uomLabel') != order.source_snapshot.get('uomLabel')
                or receipt.workshop.company_id != order.company_id):
            execution._fail('OPERATION_RECEIPT_SOURCE_INCONSISTENT', '原接收记录与工单冻结来源不一致。')
        for member in frozen['operations']:
            item = by_id.get(member.get('operationId'))
            if (item is None or item.pk in seen or member.get('operationSnapshotHash') != item.snapshot_hash
                    or member.get('workCenterId') != item.work_center_id
                    or member.get('workCenterCompanyId') != order.company_id
                    or member.get('workshopId') != receipt.workshop_id
                    or member.get('workshopDepartmentId') != frozen.get('workshopDepartmentId')
                    or member.get('source') != item.source_snapshot):
                execution._fail('OPERATION_RECEIPT_MEMBERSHIP_INCONSISTENT', '原接收冻结成员、工序或公司来源不一致。')
            seen.add(item.pk)
            membership = {
                'companyId': order.company_id, 'workOrderId': order.pk, 'productionPlanId': order.production_plan_id,
                'workOrderVersion': order.version, 'workOrderSnapshotHash': order.snapshot_hash,
                'operationId': item.pk, 'operationSnapshotHash': item.snapshot_hash,
                'workCenterId': item.work_center_id, 'originalWorkshopId': receipt.workshop_id,
                'originalWorkshopDepartmentId': member['workshopDepartmentId'],
                'receiptId': receipt.pk, 'receiptSnapshotHash': receipt.snapshot_hash, 'receiptVersion': receipt.version,
                'receiptAuditReference': fact['stateTransitionHistory'][0]['auditReference'],
                'frozenOperation': deepcopy(member),
            }
            if supplement:
                membership.update(receiptScopeKind='FORMAL_FROZEN_GROUP_SUPPLEMENT',
                    frozenGroupReceiptSupplementRef=supplement['ref'],
                    frozenGroupReceiptSupplementHash=supplement['proofHash'],
                    frozenGroupReceiptSupplementVersion=supplement['projectionVersion'])
            matches[item.pk] = (receipt, fact, membership)
    return operations, matches

def read_operation_resource(operation, *, actor=None, include_handoff=True):
    """Return one authoritative source context without creating any records."""
    _, memberships = _original_memberships(operation.work_order)
    return _read_operation_resource(operation, memberships.get(operation.pk), actor=actor, include_handoff=include_handoff)

def _read_legacy_resource(operation, original, *, actor, include_handoff):
    from pde.plan_step_context_service import _company
    order, center, process = operation.work_order, operation.work_center, operation.operation
    receipt, receipt_fact, membership = original or (None, receipts._receipt(None), None)
    workshop = center.workshop if center else None
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    current = _current_snapshot(operation, workshop)
    resource_valid = bool(center and workshop and center.company_id == workshop.company_id == order.company_id
        and _effective(center, today) and workshop.is_active
        and (center.department_id is None or center.department.company_id == order.company_id)
        and (workshop.department_id is None or workshop.department.company_id == order.company_id)
        and (center.department_id is None or workshop.department_id is None
            or center.department_id == workshop.department_id))
    master_valid = bool(process and _effective(process, today) and resource_valid
        and process.company_id == order.company_id
        and process.workshop_id in (None, workshop.pk))
    root, step = operation.root_step, operation.effective_step
    source_unchanged = bool(order.status == 'released' and root and step and root.is_active and step.is_active
        and _company(root) == _company(step) == order.company_id
        and root.routing_version_id == operation.root_routing_version_id
        and step.routing_version_id == operation.effective_routing_version_id
        and step.operation_id == operation.operation_id
        and step.work_center_id in (None, operation.work_center_id)
        and step.workshop_id in (None, workshop.pk if workshop else None))
    changed = bool(membership and (not workshop or membership['originalWorkshopId'] != workshop.pk
        or membership['originalWorkshopDepartmentId'] != workshop.department_id))
    proof = None
    if include_handoff and membership:
        from .operation_resource_handoff_service import read_handoff_projection
        projection = read_handoff_projection(operation, membership, current)
        proof = projection['currentProof']
        changed = changed or projection['requiresNewHandoff']
    issues = []
    if actor is not None and actor.company_id != order.company_id:
        issues.append('当前账号与工单不属于同一公司。')
    if not membership:
        issues.append('本工单工序尚无正式冻结接收证明。')
    if not resource_valid:
        issues.append('本工单工序尚未取得正式执行资源选择证明，当前工作中心／车间未确定。' if center is None
            else '当前工作中心、车间或部门不在有效同公司范围。')
    if not master_valid and center is not None:
        issues.append('正式工序所属车间与当前工作中心车间不一致或主数据已失效；请先完成正式主数据一致性维护。')
    if not source_unchanged:
        issues.append('当前正式步骤、工作中心声明或工单冻结来源不一致。')
    if changed and not proof:
        issues.append('本工序资源归属已变化，尚未取得新归属的正式承接证明；原接收历史保留。')
    ready = not issues
    original_workshop = receipt.workshop if receipt else None
    source = {'companyId': order.company_id, 'workOrderId': order.pk, 'workOrderNo': order.no,
        'workOrderVersion': order.version, 'workOrderSnapshotHash': order.snapshot_hash,
        'receiptId': receipt.pk if receipt else None, 'receiptSnapshotHash': receipt.snapshot_hash if receipt else None,
        'workshopId': workshop.pk if workshop else None, 'sourceOperationId': operation.pk,
        'operationSnapshotHash': operation.snapshot_hash, 'workCenterId': operation.work_center_id,
        'operation': deepcopy(operation.source_snapshot)}
    if proof is not None:
        source.update(resourceHandoffRef=proof['ref'], resourceHandoffHash=proof['proofHash'])
    facts = {'sourceReady': ready, 'changeRequired': changed, 'masterDataConsistent': master_valid,
        'originalReceiptProven': bool(membership), 'currentResourceValid': resource_valid,
        'sourceUnchanged': source_unchanged, 'blockingReasons': issues,
        'statusLabel': ('原冻结接收及新归属承接已核实' if proof else '本工序原冻结接收及当前归属一致') if ready else issues[0],
        'originalReceipt': receipt_fact,
        'originalReceiptWorkshop': {'id': original_workshop.pk, 'name': receipt.source_snapshot['workshopName'],
            'code': receipt.source_snapshot['workshopCode'],
            'departmentId': membership['originalWorkshopDepartmentId']} if original_workshop else None,
        'effectiveWorkshop': {'id': workshop.pk, 'name': workshop.name} if workshop else None,
        'effectiveReceptionAuthority': '正式归属承接' if proof else '原冻结车间接收' if membership and not changed else '待正式归属承接',
        'resourceHandoff': deepcopy(proof), 'currentSnapshotHash': execution._hash(current),
        'originalMembershipHash': execution._hash(membership) if membership else None,
        'businessWriteCount': 0, 'auditWriteCount': 0}
    return {'facts': facts, 'source': source, 'receipt': receipt, 'workshop': workshop,
        'currentSnapshot': current, 'originalMembership': membership}

def _read_base_resource(operation, original, *, actor, include_handoff):
    """Shared native resource/receipt verification, before execution admission."""
    from .operation_resource_selection_service import selection_authority, precise_receipt_history
    selection, center, selection_proof = selection_authority(operation)
    precise_history = precise_receipt_history(operation)
    precise = precise_history[0] if precise_history else None
    if selection_proof or precise:
        result = _read_precise_resource(operation, original, actor=actor, include_handoff=include_handoff,
            selection=selection, center=center, selection_proof=selection_proof, precise=precise)
    else:
        result = _read_legacy_resource(operation, original, actor=actor, include_handoff=include_handoff)
        result.update(workCenter=center, resourceSelection=None, selectionFact=selection, preciseReceipt=None,
            effectiveMembership=result['originalMembership'])
        result['facts'].update(preciseReceiptProven=False,preciseReceipt=None,resourceSelection=None,
            selectionFact=deepcopy(selection),effectiveReceiptProven=result['facts']['originalReceiptProven'])
        member=result['originalMembership']
        if member and member.get('receiptScopeKind')=='FORMAL_FROZEN_GROUP_SUPPLEMENT':
            result['source'].update({key:member[key] for key in ('frozenGroupReceiptSupplementRef',
                'frozenGroupReceiptSupplementHash','frozenGroupReceiptSupplementVersion')})
    return result

def _read_operation_resource(operation, original, *, actor, include_handoff):
    """Full context remains mandatory for every action and downstream service."""
    result=_read_base_resource(operation,original,actor=actor,include_handoff=include_handoff)
    from pde.operation_allocation_source_handoff_service import read_plan_allocation_admission
    if actor is not None and actor.company_id != operation.work_order.company_id:
        # Keep the existing explanatory, read-only denial contract. A caller
        # from another company must never cause a cross-company PDE lookup.
        from pde.operation_allocation_source_handoff_service import CONTRACT as ALLOCATION_CONTRACT
        reason='当前账号与工单不属于同一公司，未读取正式分配来源。'
        allocation={'contractVersion':ALLOCATION_CONTRACT,'companyId':operation.work_order.company_id,
            'productionPlanId':operation.work_order.production_plan_id,'routingStepId':operation.root_step_id,
            'ready':False,'actionAdmission':False,'items':[],'blockingReasons':[reason],'sourceBinding':{},
            'sourceAspectOnly':True,'statusLabel':reason,'budgetPreserved':None,
            'businessWriteCount':0,'auditWriteCount':0,'stateTransitionWriteCount':0}
        allocation['admissionHash']=_hash(allocation)
    else:
        allocation=read_plan_allocation_admission(user=actor,production_plan_id=operation.work_order.production_plan_id,
            routing_step_id=operation.root_step_id,company_id=operation.work_order.company_id)
    facts=result['facts'];facts['currentAllocationAdmission']=allocation
    if not allocation['ready']:
        facts['blockingReasons'].extend(allocation['blockingReasons']);facts['sourceReady']=False
        facts['statusLabel']='；'.join(dict.fromkeys(facts['blockingReasons']))
    if allocation.get('sourceBinding'):
        result['source'].update(deepcopy(allocation['sourceBinding']))
    _resource_display_facts(operation, result)
    return result

def _resource_display_facts(operation, context):
    """Label frozen scope and current authority without changing either proof."""
    facts = context['facts']
    center = context.get('workCenter') or operation.work_center
    selection, precise = context.get('resourceSelection'), context.get('preciseReceipt')
    accepted = facts.get('effectiveReceiptProven') is True
    changed = facts.get('changeRequired') is True
    selected = bool(context.get('selectionFact'))
    selection_label = '已选择资源' if selection else '原工单已冻结执行资源' if selected else '尚未正式选择执行资源'
    receipt_label = '已精确接收' if precise else '原冻结接收已覆盖本工序' if facts.get('originalReceiptProven') else '待本工序精确接收' if selection else '待正式接收'
    if center is None:
        handoff_label = '当前有效资源尚未确定，归属承接适用性待核实'
    elif facts.get('resourceHandoff'):
        handoff_label = '归属承接已生效'
    elif changed:
        handoff_label = '当前资源归属已变化，待正式归属承接'
    elif selection and not precise:
        handoff_label = '首次资源选择无需归属承接；请办理本工序精确接收'
    elif selection and precise:
        handoff_label = '已精确接收，当前资源归属未变化，无需归属承接'
    elif accepted:
        handoff_label = '原冻结接收归属未变化，无需归属承接'
    else:
        handoff_label = '尚无本工序接收证明；请先办理正式接收'
    def reference(proof):
        return {key:proof[key] for key in ('ref','proofHash','auditReference','timeLabel','actorLabel',
            'projectionVersion','reason','statusLabel')} if proof else None
    facts.update(
        frozenWorkCenterId=operation.work_center_id,
        frozenResourceBasisLabel='原工单冻结工作中心为空；保留原冻结历史' if operation.work_center_id is None else '原工单冻结执行资源及接收范围；保留原冻结历史',
        currentResourceBasisLabel='正式资源选择证明' if selection else '原工单冻结执行资源' if selected else '尚无当前有效执行资源证明',
        resourceSelectionStatusLabel=selection_label, receiptStatusLabel=receipt_label,
        handoffStatusLabel=handoff_label, handoffApplicable=bool(accepted and changed),
        handoffApplicabilityKnown=bool(center),
        resourceSelectionReference=reference(selection), preciseReceiptReference=reference(precise))

def _read_precise_resource(operation, original, *, actor, include_handoff, selection, center, selection_proof, precise):
    from pde.plan_step_context_service import _company
    from pde.models import WorkCenterOperationCapability
    from .operation_resource_selection_service import validate_precise_receipt
    order,process=operation.work_order,operation.operation
    old_receipt,old_fact,original_membership=original or (None,receipts._receipt(None),None)
    receipt=old_receipt;receipt_fact=old_fact;membership=deepcopy(original_membership)
    workshop=center.workshop if center else None
    current=_current_snapshot(operation,workshop,effective_center=center)
    if precise:
        receipt,precise=validate_precise_receipt(operation,selection,precise)
        receipt_fact=receipts._receipt(receipt)
        accepted=precise['snapshot']['currentResource']
        membership={'membershipKind':'PRECISE_OPERATION_RECEIPT','originalMembership':False,
            'companyId':order.company_id,'workOrderId':order.pk,'productionPlanId':order.production_plan_id,
            'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
            'operationId':operation.pk,'operationSnapshotHash':operation.snapshot_hash,
            'workCenterId':accepted['workCenter']['id'],'originalWorkshopId':accepted['workshop']['id'],
            'originalWorkshopDepartmentId':accepted['workshop']['departmentId'],
            'receiptId':receipt.pk,'receiptSnapshotHash':receipt.snapshot_hash,'receiptVersion':receipt.version,
            'receiptAuditReference':precise['auditReference'],'frozenOperation':deepcopy(operation.source_snapshot),
            'resourceSelectionRef':selection['ref'],'resourceSelectionHash':selection['proofHash'],
            'preciseReceiptRef':precise['ref'],'preciseReceiptHash':precise['proofHash']}
    today=timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    capability=WorkCenterOperationCapability.objects.filter(work_center=center,
        operation_id=operation.operation_id,is_active=True).first() if center else None
    resource_valid=bool(center and workshop and center.company_id==workshop.company_id==order.company_id
        and _effective(center,today) and workshop.is_active and capability and _effective(capability,today)
        and (center.department_id is None or center.department.company_id==order.company_id)
        and (workshop.department_id is None or workshop.department.company_id==order.company_id)
        and (center.department_id is None or workshop.department_id is None or center.department_id==workshop.department_id))
    master_valid=bool(resource_valid and _effective(process,today) and process.company_id in (None,order.company_id)
        and process.workshop_id in (None,workshop.pk))
    root,step=operation.root_step,operation.effective_step
    source_unchanged=bool(order.status=='released' and root and step and root.is_active and step.is_active
        and _company(root)==_company(step)==order.company_id and root.routing_version_id==operation.root_routing_version_id
        and step.routing_version_id==operation.effective_routing_version_id and step.operation_id==operation.operation_id
        and step.work_center_id in (None,center.pk if center else None)
        and step.workshop_id in (None,workshop.pk if workshop else None))
    changed=bool(membership and (not workshop or membership['originalWorkshopId']!=workshop.pk
        or membership['originalWorkshopDepartmentId']!=workshop.department_id))
    handoff=None
    if include_handoff and membership:
        from .operation_resource_handoff_service import read_handoff_projection
        projected=read_handoff_projection(operation,membership,current)
        handoff=projected['currentProof'];changed=changed or projected['requiresNewHandoff']
    issues=[]
    if actor is not None and actor.company_id!=order.company_id:issues.append('当前账号与工单不属于同一公司。')
    if not precise:issues.append('资源已正式选择，尚无本工序绑定该选择版本的精确接收证明。')
    if not resource_valid:issues.append('当前所选工作中心、工序能力、车间或部门不在有效同公司范围。')
    if not master_valid:issues.append('正式工艺、所选工作中心与当前车间不一致或已失效，请办理正式维护／承接。')
    if not source_unchanged:issues.append('当前正式步骤、声明资源或工单冻结来源不一致。')
    if precise and _hash(precise['snapshot']['currentResource'])!=_hash(current):changed=True
    if changed and not handoff:issues.append('已选择资源归属已变化，精确接收历史保留；当前新归属尚无正式承接证明。')
    source={'companyId':order.company_id,'workOrderId':order.pk,'workOrderNo':order.no,
        'workOrderVersion':order.version,'workOrderSnapshotHash':order.snapshot_hash,
        'receiptId':receipt.pk if receipt else None,'receiptSnapshotHash':receipt.snapshot_hash if receipt else None,
        'workshopId':workshop.pk if workshop else None,'sourceOperationId':operation.pk,
        'operationSnapshotHash':operation.snapshot_hash,'workCenterId':center.pk if center else None,
        'operation':deepcopy(operation.source_snapshot)}
    if selection_proof:source.update(executionResourceSelectionRef=selection_proof['ref'],
        executionResourceSelectionHash=selection_proof['proofHash'],executionResourceSelectionVersion=selection_proof['projectionVersion'])
    if precise:source.update(preciseOperationReceiptRef=precise['ref'],preciseOperationReceiptHash=precise['proofHash'],
        preciseOperationReceiptVersion=precise['projectionVersion'])
    if handoff:source.update(resourceHandoffRef=handoff['ref'],resourceHandoffHash=handoff['proofHash'])
    original_workshop=old_receipt.workshop if old_receipt else None
    authority='正式归属承接＋逐工序精确接收' if handoff else '正式资源选择＋逐工序精确接收' if precise else '待逐工序精确接收'
    facts={'sourceReady':not issues,'changeRequired':changed,'masterDataConsistent':master_valid,
        'originalReceiptProven':bool(original_membership),'preciseReceiptProven':bool(precise),
        'effectiveReceiptProven':bool(membership),'currentResourceValid':resource_valid,'sourceUnchanged':source_unchanged,
        'blockingReasons':issues,'statusLabel':authority+'已核实' if not issues else '；'.join(issues),
        'originalReceipt':old_fact,'receiptAnchor':receipt_fact,'preciseReceipt':deepcopy(precise),
        'resourceSelection':deepcopy(selection_proof),'selectionFact':deepcopy(selection),
        'originalReceiptWorkshop':{'id':original_workshop.pk,'name':old_receipt.source_snapshot['workshopName'],
            'code':old_receipt.source_snapshot['workshopCode'],'departmentId':original_membership['originalWorkshopDepartmentId']}
            if original_workshop else None,
        'effectiveWorkshop':{'id':workshop.pk,'name':workshop.name} if workshop else None,
        'effectiveReceptionAuthority':authority,'resourceHandoff':deepcopy(handoff),'currentSnapshotHash':_hash(current),
        'originalMembershipHash':_hash(original_membership) if original_membership else None,
        'effectiveMembershipHash':_hash(membership) if membership else None,'businessWriteCount':0,'auditWriteCount':0}
    return {'facts':facts,'source':source,'receipt':receipt,'workshop':workshop,'workCenter':center,
        'currentSnapshot':current,'originalMembership':original_membership,'effectiveMembership':membership,
        'resourceSelection':selection_proof,'selectionFact':selection,'preciseReceipt':precise}


# Native formal continuation: individually restored symbols; existing proofs preserved.
def read_order_resources(order, *, actor=None, include_handoff=True):
    """Use one fully verified frozen membership set for an order projection."""
    from pde.operation_allocation_source_handoff_service import allocation_admission_context
    with allocation_admission_context(user=actor,company_id=order.company_id):
        operations, memberships = _original_memberships(order)
        return [(operation, _read_operation_resource(operation, memberships.get(operation.pk),
            actor=actor, include_handoff=include_handoff)) for operation in operations]

def read_order_resource_summaries(order, *, actor):
    """Receiving-list DTO only; never a context accepted by action validators.

This reader verifies the same resource/receipt proofs, while explicitly not
requesting allocation, budget or execution admission. It returns no source
dictionary or membership context that could be used to authorize an action.
"""
    if actor is None or not actor.is_active or actor.company_id!=order.company_id:
        execution._fail('OPERATION_RESOURCE_SUMMARY_SCOPE_DENIED','资源及接收摘要仅限当前账号所在公司工单。',403)
    operations,memberships=_original_memberships(order)
    keys=('originalReceiptProven','preciseReceiptProven','effectiveReceiptProven','currentResourceValid',
        'masterDataConsistent','sourceUnchanged','changeRequired','originalReceiptWorkshop','effectiveWorkshop',
        'effectiveReceptionAuthority','frozenWorkCenterId','frozenResourceBasisLabel','currentResourceBasisLabel',
        'resourceSelectionStatusLabel','receiptStatusLabel','handoffStatusLabel','handoffApplicable',
        'handoffApplicabilityKnown','resourceSelectionReference','preciseReceiptReference','blockingReasons')
    summaries={}
    for operation in operations:
        context=_read_base_resource(operation,memberships.get(operation.pk),actor=actor,include_handoff=True)
        _resource_display_facts(operation,context)
        facts=context['facts']
        summaries[operation.pk]={**{key:deepcopy(facts[key]) for key in keys},
            'contractVersion':'PCE-RESOURCE-RECEIPT-SUMMARY-V1','summaryOnly':True,
            'allocationAdmissionIncluded':False,'executionAdmissionIncluded':False,
            'currentAllocationAdmission':None,'sourceReady':None,
            'statusLabel':'资源与接收证明摘要；执行来源准入未请求；'+facts['receiptStatusLabel'],
            'businessWriteCount':0,'auditWriteCount':0}
        proof=facts.get('resourceHandoff')
        summaries[operation.pk]['resourceHandoffReference']=({key:deepcopy(proof[key]) for key in
            ('ref','proofHash','auditReference','actorId','timeLabel','statusLabel')} if proof else None)
    return summaries
