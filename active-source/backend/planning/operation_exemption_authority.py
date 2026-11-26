

# Native formal continuation: individually restored symbols; existing proofs preserved.
from .work_order_execution_service import _fail, _hash, read_verified_member_ids

VERSION_KEYS = ('originalManufacturingOutputId', 'effectiveManufacturingOutputId',
    'originalRoutingVersionId', 'effectiveRoutingVersionId', 'rootRoutingStepId',
    'effectiveRoutingStepId', 'bindingId', 'sourceBaselineId', 'mainCalculationId', 'sourceSelection')

def _denied(code, message):
    _fail('OPERATION_EXEMPTION_' + code, message)

def _load_scope(operation, actor):
    """Native internal source read; successor needs no PDE maintenance grant."""
    from pde.capacity_evidence_read_scope import evidence_cache
    from pde.operation_requirement_service import _read_once
    from pde.operation_workload_source_service import _scope_context

    from .work_order_models import ProductionWorkOrder, ProductionWorkOrderOperation
    from pde.plan_step_context_service import resolve_step_context, version_fact
    if (actor is None or not actor.is_active or actor.company_id != operation.work_order.company_id):
        _denied('SCOPE_DENIED', '免执行来源仅限有效账号所在公司及本工单范围。')
    candidates = ProductionWorkOrderOperation.objects.filter(pk=operation.pk,
        work_order_id=operation.work_order_id, work_order__company_id=actor.company_id)
    related = ('operation', 'root_step', 'effective_step')
    evidence = evidence_cache(actor.company_id)
    if evidence is None:
        stored = candidates.select_related('work_order__production_plan', *related).first()
    else:
        stored = _read_once(evidence, ('exemption_operation_raw', actor.company_id,
            operation.work_order_id, operation.pk), lambda: candidates.select_related(*related).first())
        if stored is not None:
            stored = copy(stored)
            def read_work_order():
                return ProductionWorkOrder.objects.select_related('source_schedule', 'production_plan').get(
                    pk=stored.work_order_id, company_id=actor.company_id)

            persisted_order = _read_once(
                evidence, ('exemption_work_order_raw', actor.company_id, stored.work_order_id), read_work_order)
            stored.work_order = copy(persisted_order)
    if stored is None or stored.snapshot_hash != operation.snapshot_hash:
        _denied('SOURCE_CHANGED', '免执行对象或冻结工序来源不一致。')
    members = read_verified_member_ids(stored.work_order)
    if stored.pk not in members or stored.work_order.status != 'released':
        _denied('SOURCE_CHANGED', '免执行工序不属于有效已下达工单的完整冻结来源。')
    from .workshop_reception_read_projection import current_native_read_cache
    cache=current_native_read_cache(actor)
    context = _scope_context(actor, stored.work_order.production_plan_id, stored.root_step_id,
        **({'_read_cache':cache} if cache is not None else {}))
    plan, output, item, base, step, kind, applicability = context
    version = version_fact(resolve_step_context(stored.work_order.production_plan, stored.root_step_id, user=actor,
        **({'read_cache':cache} if cache is not None else {})))
    frozen = stored.source_snapshot.get('frozenStep', {})
    old_version = frozen.get('engineeringVersion')
    if (not isinstance(old_version, dict) or any(old_version.get(key) != version.get(key) for key in VERSION_KEYS)
            or plan.pk != stored.work_order.production_plan_id or step.pk != stored.effective_step_id
            or step.routing_version_id != stored.effective_routing_version_id
            or step.operation_id != stored.operation_id or not step.is_active
            or stored.source_snapshot.get('operationId') != stored.operation_id):
        _denied('VERSION_CHANGED', '免执行的工单、步骤、正式工艺或当前工程来源版本不一致。')
    return stored, context, version, frozen

# Native formal exemption proof recovery.
from copy import copy, deepcopy

from django.core.exceptions import ValidationError

from masterdata.models import MasterDataWriteRequest

from system.models import OrganizationOperatingAuditRecord

from .services import PlanningBusinessError

CONTRACT = 'PCE-OPERATION-FORMAL-EXEMPTION-AUTHORITY-V1'

PROOF_TYPE = 'FORMAL_EXEMPTION'

def _mapping(value, *, optional=False):
    if value is None and optional:
        return {}
    if not isinstance(value, dict):
        _denied('AUDIT_UNPROVEN', '免执行来源中的正式审计或账本结构损坏，请核对原始证明。')
    return value

def _manual_proof(operation, context, applicability):
    from pde.routing_manual_applicability_service import (RoutingManualApplicabilityService,
        MANUAL_ACTION, MANUAL_CONTRACT_VERSION, MANUAL_SOURCE_TYPE)
    from pde.routing_version_successor_service import ROUTING_PERMISSION
    from pde.plan_step_context_service import effective_baseline
    plan, output, item, base, step, _, _ = context
    decision = RoutingManualApplicabilityService.resolve_for_step(step, engineering_calculation=base,
        order_engineering_instance=base.engineering_instance, order_engineering_baseline=effective_baseline(plan),
        bom_version=output.bom_version)
    if (decision.get('status') != 'RESOLVED' or decision.get('decision') != 'NO'
            or decision.get('result') != 'NOT_APPLICABLE'
            or decision.get('auditId') != applicability.get('manualDecisionAuditId')):
        _denied('MANUAL_UNPROVEN', '本工序缺少与精确订单工程范围一致的正式不适用判断。')
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=decision['auditId'],
        organization_id=operation.work_order.company_id, actor_id=decision['confirmedByUserId'],
        action_code=MANUAL_ACTION, target_type='RoutingVersion', target_id=step.routing_version_id).first()
    after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
    state = _mapping(after.get('state'))
    scope, audited = state.get('manualDecisionContext'), state.get('manualDecision')
    authorization, chain, imported = after.get('authorization'), after.get('executionChain'), after.get('importContext')
    if (not audit or not isinstance(scope, dict) or not isinstance(audited, dict)
            or scope.get('organizationId') != operation.work_order.company_id
            or scope.get('salesOrderItemId') != item.pk or scope.get('engineeringCalculationId') != base.pk
            or scope.get('orderEngineeringInstanceId') != base.engineering_instance_id
            or scope.get('orderEngineeringBaselineId') != effective_baseline(plan).pk
            or scope.get('bomVersionId') != output.bom_version_id
            or scope.get('routingVersionId') != step.routing_version_id
            or audited.get('decision') != 'NO' or audited.get('confirmedByUserId') != audit.actor_id
            or not isinstance(audited.get('note'), str) or audited['note'][:300] != audit.reason
            or state.get('routingStepId') != step.pk
            or state.get('conditionCode') != applicability.get('conditionCode')
            or not isinstance(authorization, dict) or authorization.get('allowed') is not True
            or authorization.get('actionCode') != ROUTING_PERMISSION
            or str(authorization.get('organizationId')) != str(operation.work_order.company_id)
            or not isinstance(chain, dict) or chain.get('account') != decision.get('confirmedByUsername')
            or any(type(chain.get(key)) is not int or chain[key] <= 0 for key in ('employeeId', 'positionId', 'responsibilityId'))
            or not isinstance(imported, dict) or imported.get('contractVersion') != MANUAL_CONTRACT_VERSION
            or imported.get('sourceType') != MANUAL_SOURCE_TYPE or imported.get('routingStepId') != step.pk
            or imported.get('conditionCode') != applicability.get('conditionCode')):
        _denied('AUDIT_UNPROVEN', '免执行人工判断的正式审计、责任链或精确来源不一致。')
    ledger = MasterDataWriteRequest.objects.select_related('source_identity').filter(
        pk=decision.get('writeRequestId'), organization_id=operation.work_order.company_id,
        action_code=MANUAL_ACTION, entity_type='routing-versions', target_entity_id=str(step.routing_version_id)).first()
    identity = ledger.source_identity if ledger else None
    fingerprint = {'routingVersionId': step.routing_version_id, 'contextIdentityHash': scope.get('identityHash'),
        'conditionCode': applicability['conditionCode']}
    expected_external = f"RoutingVersion:{step.routing_version_id}:{scope.get('contextKey')}:{applicability['conditionCode']}"
    result = ledger.result if ledger and isinstance(ledger.result, dict) else {}
    before_state = _mapping(_mapping(audit.before_snapshot).get('state'))
    previous = _mapping(before_state.get('applicability'), optional=True)
    previous = _mapping(previous.get('manualStepApplicability'), optional=True)
    previous = _mapping(previous.get('contexts'), optional=True)
    previous = _mapping(previous.get(scope.get('contextKey')), optional=True)
    previous = _mapping(previous.get('decisions'), optional=True)
    previous = _mapping(previous.get(applicability['conditionCode']), optional=True)
    expected_payload = {'routingVersionId': step.routing_version_id, 'routingStepId': step.pk,
        'contextKey': scope.get('contextKey'), 'contextIdentityHash': scope.get('identityHash'),
        'conditionCode': applicability['conditionCode'], 'decision': 'NO', 'note': audited['note'],
        'expectedAuditId': previous.get('auditId')}
    if (not ledger or ledger.status != 'COMMITTED' or not identity
            or not isinstance(ledger.audit_metadata, dict) or not isinstance(identity.audit_metadata, dict)
            or result.get('routingVersionId') != step.routing_version_id or result.get('routingStepId') != step.pk
            or result.get('contextKey') != scope.get('contextKey') or result.get('conditionCode') != applicability['conditionCode']
            or result.get('decision') != 'NO' or result.get('auditId') != audit.pk
            or result.get('confirmedByUserId') != audit.actor_id or result.get('writeRequestId') != ledger.pk
            or result.get('sourceIdentityId') != identity.pk
            or identity.organization_id != operation.work_order.company_id or identity.source_system != 'PCE_SYSTEM'
            or identity.source_type != 'ROUTING_VERSION_CONTROLLED_CHANGE'
            or identity.source_object_type != 'ROUTING_MANUAL_APPLICABILITY_DECISION'
            or identity.external_id != expected_external or identity.target_entity_type != 'routing-versions'
            or identity.target_entity_id != str(step.routing_version_id) or identity.mapping_status != 'MATCH'
            or identity.source_fingerprint != _hash(fingerprint)
            or identity.audit_metadata.get('fingerprintPayload') != fingerprint
            or imported.get('sourceFingerprint') != identity.source_fingerprint
            or ledger.request_hash != _hash(expected_payload)
            or ledger.audit_metadata.get('operatorId') != audit.actor_id):
        _denied('LEDGER_UNPROVEN', '免执行判断缺少已提交、同对象同人员的账本及正式来源身份。')
    return {'sourceType': MANUAL_SOURCE_TYPE, 'decision': 'NO', 'conditionCode': applicability['conditionCode'],
        'context': deepcopy(scope), 'auditReference': f'OrganizationOperatingAuditRecord:{audit.pk}',
        'auditSnapshotHash': _hash(after), 'writeRequestId': ledger.pk, 'requestHash': ledger.request_hash,
        'sourceIdentityId': identity.pk, 'sourceFingerprint': identity.source_fingerprint,
        'confirmedById': audit.actor_id, 'confirmedAt': decision['confirmedAt'],
        'reason': audit.reason, 'stateMachineConsistent': True}

def _object_proof(context, applicability):
    """The native resolver verifies original and append-only correction chains."""
    objects = applicability.get('objectApplicability')
    if (not isinstance(objects, dict) or objects.get('complete') is not True or objects.get('factSource') != 'server'
            or objects.get('result') != 'NOT_APPLICABLE' or not objects.get('fullBaselineItemIds')
            or set(objects['fullBaselineItemIds']) != set(objects.get('excludedBaselineItemIds', []))
            or objects.get('requiredBaselineItemIds') or objects.get('unknownBaselineItemIds')
            or len(objects.get('objects', [])) != len(objects['fullBaselineItemIds'])):
        _denied('OBJECT_UNPROVEN', '正式对象不适用范围未完整覆盖本工序，不能免执行。')
    return {'sourceType': 'FORMAL_OBJECT_APPLICABILITY', 'objectAuthority': deepcopy(objects),
        'sourceHash': _hash(objects), 'stateMachineConsistent': True}

def _applicability_identity(value):
    # Daily-capacity display adds this translated label to the same persisted
    # decision. Identity still retains every decision, source, version, hash,
    # audit and request field; display enrichment cannot change eligibility.
    result=deepcopy(value)
    if isinstance(result,dict):
        for row in (result.get('objectApplicability') or {}).get('objects',[]):
            row.pop('decisionLabel',None)
    return result

def read_operation_exemption(operation, *, actor):
    """Derive a stable certificate; no writes, new approval, or execution claim."""
    try:
        operation, context, version, frozen = _load_scope(operation, actor)
        applicability = context[-1]
        original = frozen.get('applicability')
        if isinstance(original, dict) and original.get('result') == applicability.get('result') == 'REQUIRED':
            _denied('EXECUTION_REQUIRED', '本工序正式要求实际执行，不能以免执行证明替代。')
        if (not isinstance(original, dict) or original.get('result') != 'NOT_APPLICABLE'
                or applicability.get('result') != 'NOT_APPLICABLE'
                or applicability.get('formalApplicabilityValidated') is not True
                or applicability.get('conditionalExecution') or applicability.get('pendingCode')
                or _hash(_applicability_identity(original)) != _hash(_applicability_identity(applicability))):
            _denied('APPLICABILITY_PENDING', '适用性未知、待触发或来源已变化，尚无本工序正式免执行证明。')
        if applicability.get('objectApplicability') is not None:
            proof = _object_proof(context, applicability)
        elif applicability.get('manualDecision') == 'NO':
            proof = _manual_proof(operation, context, applicability)
        else:
            _denied('AUTHORITY_UNSUPPORTED', '该不适用来源尚无本执行链可独立回读的完整证明，不能仅凭标签免执行。')
        snapshot = {'companyId': operation.work_order.company_id, 'workOrderId': operation.work_order_id,
            'workOrderVersion': operation.work_order.version, 'workOrderSnapshotHash': operation.work_order.snapshot_hash,
            'operationId': operation.pk, 'formalProcessId': operation.operation_id, 'sequence': operation.sequence,
            'rootStepId': operation.root_step_id, 'effectiveStepId': operation.effective_step_id,
            'rootRoutingVersionId': operation.root_routing_version_id, 'effectiveRoutingVersionId': operation.effective_routing_version_id,
            'operationSnapshotHash': operation.snapshot_hash, 'engineeringVersion': deepcopy(version),
            'applicabilityHash': _hash(applicability), 'authority': proof}
        source_hash = _hash(snapshot)
        return {'contractVersion': CONTRACT, 'proofType': PROOF_TYPE, 'companyId': operation.work_order.company_id,
            'workOrderId': operation.work_order_id, 'operationId': operation.pk, 'formalProcessId': operation.operation_id,
            'sequence': operation.sequence, 'sourceHash': source_hash, 'proofHash': _hash({'proofType': PROOF_TYPE, 'snapshot': snapshot}),
            'ref': f'FormalExemption:ProductionWorkOrderOperation:{operation.pk}:{source_hash}',
            'snapshot': snapshot, 'actualExecution': False, 'actualStart': False, 'actualReport': False,
            'persistenceAuthority': 'EXISTING_PDE_FORMAL_FACTS', 'statusLabel': '本工序正式不适用，免执行来源已核实',
            'businessWriteCount': 0, 'auditWriteCount': 0, 'stateMachineConsistent': True}
    except PlanningBusinessError:
        raise
    except Exception as error:
        if not (isinstance(error, (ValidationError, KeyError, TypeError, AttributeError)) or hasattr(error, 'code')):
            raise
        _denied('SOURCE_UNPROVEN', '正式适用性、工程来源或审计证明未通过核验：' + str(getattr(error, 'message', error)))
