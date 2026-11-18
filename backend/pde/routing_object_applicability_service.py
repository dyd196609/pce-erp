"""Immutable, plan-bound object decisions over an existing released route.

This service never changes a route, creates engineering facts or generates
operation requirements.  A decision is an authorized business fact; its cited
source fact/rules prove identity and provenance, not a name-based classifier.
"""
from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from copy import deepcopy

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import ProductionPlan
from system.models import OrganizationOperatingAuditRecord, User

from .engineering_rule_foundation import specification_hash
from .models import (
    EngineeringDerivedFact, EngineeringRuleDefinition, OrderEngineeringBaselineItem,
    ProductManufacturingOutput, RoutingStep,
)
from .production_foundation_service import _audit, _snapshot
from .plan_step_context_service import effective_calculation, effective_baseline, source_selection


CONTRACT_VERSION = "PCE-ROUTING-OBJECT-APPLICABILITY-V1"
BASIS_CONTRACT_VERSION = "PCE-ROUTING-OBJECT-APPLICABILITY-BASIS-V1"
ACTION = "pde.routing_step.confirm_object_applicability"
ENTITY_TYPE = "routing-step-object-applicability"
SOURCE_OBJECT_TYPE = "ROUTING_STEP_OBJECT_APPLICABILITY"
REQUIRED, NOT_APPLICABLE, PENDING = "REQUIRED", "NOT_APPLICABLE", "PENDING"
DECISIONS = {REQUIRED, NOT_APPLICABLE, PENDING}


def _fail(code, message, **details):
    # Lazy imports avoid a cycle through the shared applicability resolver.
    from .routing_version_successor_service import RoutingVersionChangeError
    raise RoutingVersionChangeError(code, message, details)


def _hash(value):
    from .routing_version_successor_service import _canonical_hash
    return _canonical_hash(value)


def _model():
    from .models import RoutingStepObjectApplicability
    return RoutingStepObjectApplicability


def _positive_id(value, field):
    if type(value) is not int or value <= 0:
        _fail("OBJECT_APPLICABILITY_ID_INVALID", "对象适用性身份必须为正整数FK。", field=field)
    return value


def _hash_token(value, field):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _fail("OBJECT_APPLICABILITY_HASH_INVALID", "对象适用性必须绑定完整SHA256。", field=field)
    return value


def _organization_matches(value, company_id):
    # AuthorizationService.decide serializes organizationId as decimal text;
    # native integer identities are also legal. Reject bool and coercion.
    return ((type(value) is int and value == company_id)
        or (type(value) is str and value == str(company_id)))


def _load_scope(production_plan_id, routing_step_id, *, lock=False, read_cache=None):
    """Read the full fixed order-line scope, never infer it from allocations."""
    _positive_id(production_plan_id, "productionPlanId")
    _positive_id(routing_step_id, "routingStepId")
    if lock:
        # Lock non-null roots separately; no FOR UPDATE over nullable joins.
        list(ProductionPlan.objects.select_for_update().filter(pk=production_plan_id))
    plan = ProductionPlan.objects.select_related(
        "material", "planning_requirement__material", "planning_requirement__demand__material",
        "planning_requirement__demand__department",
        "planning_requirement__demand__sales_order_item__sales_order",
        "planning_requirement__demand__manufacturing_output__engineering_calculation__source_record",
        "planning_requirement__demand__manufacturing_output__engineering_calculation__engineering_instance",
        "planning_requirement__demand__manufacturing_output__order_engineering_baseline__sales_order",
        "planning_requirement__demand__manufacturing_output__routing_version__routing",
        "planning_requirement__demand__manufacturing_output__order_engineering_instance",
        "planning_requirement__demand__manufacturing_output__bom_version",
        "planning_requirement__demand__manufacturing_output__engineering_document_version",
    ).filter(pk=production_plan_id).first()
    if plan is None:
        _fail("OBJECT_APPLICABILITY_PLAN_MISSING", "生产计划不存在。")
    requirement, demand = plan.planning_requirement, plan.planning_requirement.demand
    from .plan_step_context_service import resolve_step_context, bind_plan_context, PlanStepContextError
    try:
        version_context = resolve_step_context(plan, routing_step_id,read_cache=None if lock else read_cache)
    except PlanStepContextError as error:
        _fail(error.code, error.message, **error.details)
    plan = bind_plan_context(plan, version_context)
    routing_step_id = version_context['step'].pk
    item, output = demand.sales_order_item, version_context['output']
    if not item or not output:
        _fail("OBJECT_APPLICABILITY_SCOPE_MISSING", "计划必须固定订单行和制造输出。")
    company_id = item.sales_order.company_id
    base, baseline = effective_calculation(plan), effective_baseline(plan)
    if lock:
        list(ProductManufacturingOutput.objects.select_for_update().filter(pk=output.pk))
        if baseline is not None:
            list(type(baseline).objects.select_for_update().filter(pk=baseline.pk))
    if (plan.status != "confirmed" or plan.planned_qty != requirement.net_required_qty
        or len({plan.material_id, requirement.material_id, demand.material_id, item.material_id}) != 1
        or any(material.company_id != company_id for material in
               (plan.material, requirement.material, demand.material, item.material))
        or demand.department.company_id != company_id):
        _fail("OBJECT_APPLICABILITY_PLAN_INVALID", "计划状态、净需求数量或物料组织范围不一致。")
    if (not base or not baseline or base.scope != "order_engineering" or base.status != "completed"
        or base.company_id != company_id or base.sales_order_item_id != item.pk
        or base.engineering_instance_id != output.order_engineering_instance_id
        or not base.source_record_id or base.source_record.status != "confirmed"
        or base.source_record.company_id != company_id
        or base.engineering_instance.source_record_id != base.source_record_id
        or base.engineering_instance.sales_order_item_id != item.pk
        or base.engineering_instance.company_id != company_id
        or baseline.company_id != company_id or production_status(baseline) != "confirmed"
        or baseline.sales_order_id != item.sales_order_id
        or output.release_status != "released_to_manufacturing"
        or output.routing_version.status != "released"):
        _fail("OBJECT_APPLICABILITY_SCOPE_INVALID", "制造输出、主核算、基线和正式来源必须属于同一有效固定范围。")
    output.clean()
    step = RoutingStep.objects.select_related("operation").filter(
        pk=routing_step_id, routing_version_id=output.routing_version_id).first()
    route = output.routing_version.routing
    if not step or not step.is_active or not route or route.company_id != company_id:
        _fail("OBJECT_APPLICABILITY_STEP_INVALID", "步骤必须为固定路线版本中同公司有效步骤。")
    if lock:
        list(OrderEngineeringBaselineItem.objects.select_for_update().filter(baseline=baseline))
    objects = list(OrderEngineeringBaselineItem.objects.select_related("design_item", "source_record")
        .filter(baseline=baseline, design_item__sales_order_item_id=item.pk)
        .order_by("source_attribute_id", "design_item_id", "pk"))
    from .formal_engineering_continuation_service import _baseline_reference
    reference = _baseline_reference(baseline, objects, read_cache=None if lock else read_cache)
    if not objects or not isinstance(base.trace, dict) or base.trace.get("baselineReference") != reference:
        _fail("OBJECT_APPLICABILITY_BASELINE_DRIFT", "主核算的完整基线及对象范围Hash与当前固定基线不一致。")
    for obj in objects:
        design = obj.design_item
        if (not obj.confirmable or obj.source_record_id != base.source_record_id
            or obj.source_attribute_id != design.source_attribute_id
            or obj.source_attribute.sales_order_item_id != item.pk
            or design.company_id != company_id or design.source_record_id != base.source_record_id
            or obj.design_item_version != design.version
            or obj.source_version_snapshot != base.source_record.source_version
            or obj.source_content_hash_snapshot != base.source_record.content_hash
            or design.source_version != base.source_record.source_version
            or design.source_content_hash != base.source_record.content_hash
            or _hash(obj.content_snapshot) != obj.content_hash):
            _fail("OBJECT_APPLICABILITY_OBJECT_DRIFT", "完整对象范围的来源、版本或内容Hash不一致。", baselineItemId=obj.pk)
    for name in ("input_hash", "rule_graph_hash", "result_hash"):
        _hash_token(getattr(base, name), name)
    _hash_token(base.source_record.content_hash, "sourceContentHash")
    _hash_token(baseline.snapshot_hash, "baselineSnapshotHash")
    return {"company_id": company_id, "plan": plan, "demand": demand, "item": item,
        "output": output, "base": base, "baseline": baseline, "step": step,
        "objects": objects, "reference": reference}


def _context_common(scope):
    """Project one already-proved scope before a pure object-context batch."""
    plan, output, base, baseline, step = (scope[k] for k in ("plan", "output", "base", "baseline", "step"))
    result = {
        "contractVersion": CONTRACT_VERSION, "organizationId": scope["company_id"],
        "productionPlanId": plan.pk, "productionPlanQuantity": str(plan.planned_qty),
        "productionPlanStatus": plan.status, "netRequiredQuantity": str(plan.planning_requirement.net_required_qty),
        "planningRequirementId": plan.planning_requirement_id, "demandId": scope["demand"].pk,
        "salesOrderId": scope["item"].sales_order_id, "salesOrderItemId": scope["item"].pk,
        "materialId": scope["item"].material_id, "orderQuantity": str(scope["item"].quantity),
        "orderUomId": scope["item"].uom_id, "manufacturingOutputId": output.pk,
        "bomVersionId": output.bom_version_id, "bomRevision": output.bom_version.revision,
        "engineeringDocumentVersionId": output.engineering_document_version_id,
        "orderEngineeringInstanceId": base.engineering_instance_id,
        "mainCalculationId": base.pk, "calculationRevision": base.revision,
        "calculationInputHash": base.input_hash, "calculationRuleGraphHash": base.rule_graph_hash,
        "calculationResultHash": base.result_hash, "baselineId": baseline.pk,
        "baselineSnapshotHash": baseline.snapshot_hash, "selectedItemHash": scope["reference"]["selectedItemHash"],
        "routingId": output.routing_version.routing_id, "routingVersionId": output.routing_version_id,
        "routingVersion": output.routing_version.routing_version, "routingRevision": output.routing_version.revision,
        "routingStepId": step.pk, "sequence": step.sequence, "operationId": step.operation_id,
        "sourceRecordId": base.source_record_id, "sourceVersion": base.source_record.source_version,
        "sourceContentHash": base.source_record.content_hash,
    }
    selection = source_selection(plan)
    if selection is not None:
        # The private common projection is consumed synchronously below;
        # _object_context gives every returned row its independent JSON copy.
        result['sourceSelection'] = selection
    return result


def _object_context(common, obj):
    result = {**common, "baselineItemId": obj.pk, "designItemId": obj.design_item_id,
        "designItemVersion": obj.design_item_version, "objectContentHash": obj.content_hash}
    if 'sourceSelection' in result:
        # Each historical formalContext keeps its own mutable proof JSON.
        result['sourceSelection'] = deepcopy(result['sourceSelection'])
    return result


def _context(scope, obj):
    """Retain the original single-object entry and its fresh source guard."""
    return _object_context(_context_common(scope), obj)


def _contexts(scope, objects):
    """Project all objects with one source guard in this pure, local loop.

    The caller has already validated the complete scope and object set. This
    does not retain a context across calls or skip a native source proof: it
    only avoids rechecking the same unchanged plan model for every projection.
    No callbacks, database writes or external cache occur between objects.
    """
    objects = tuple(objects)
    if not objects:
        return []
    common = _context_common(scope)
    return [_object_context(common, obj) for obj in objects]


def _trace_identity(trace, name):
    trace = trace if isinstance(trace, dict) else {}
    group = trace.get("group") if isinstance(trace.get("group"), dict) else {}
    values = [v for v in (trace.get(name), group.get(name)) if v is not None]
    if any(type(v) is not int or v <= 0 for v in values) or len(set(values)) > 1:
        _fail("OBJECT_APPLICABILITY_SOURCE_OBJECT_INVALID", "正式事实的对象身份无效或冲突。", field=name)
    return values[0] if values else None


def _source_proof(scope, obj, fact_id):
    from .engineering_fact_extension_service import _source_snapshot
    from .operation_requirement_service import _active
    fact = EngineeringDerivedFact.objects.select_related("source_detail__rule", "rule").filter(
        pk=_positive_id(fact_id, "sourceFactId"), calculation_id=scope["base"].pk).first()
    if (not fact or not fact.rule_id or fact.rule.status != "released" or not _active(fact.rule)
        or _trace_identity(fact.trace, "baselineItemId") != obj.pk
        or _trace_identity(fact.trace, "designItemId") != obj.design_item_id
        or _trace_identity(fact.trace, "baselineId") not in (None, scope["baseline"].pk)):
        _fail("OBJECT_APPLICABILITY_SOURCE_OBJECT_INVALID", "依据事实必须为主核算中当前精确对象的有效正式事实。")
    trace = fact.trace if isinstance(fact.trace, dict) else {}
    if trace.get("baselineContentHash") not in (None, obj.content_hash):
        _fail("OBJECT_APPLICABILITY_SOURCE_HASH_DRIFT", "依据事实的对象内容Hash不一致。")
    snapshot = _source_snapshot(fact, scope["base"])
    return {"id": fact.pk, "sourceSnapshotHash": _hash(snapshot), "snapshot": snapshot}


@transaction.atomic
def build_context(production_plan_id, routing_step_id, baseline_item_id):
    """Pure preparation: expose authoritative identity and native source proofs."""
    scope = _load_scope(production_plan_id, routing_step_id)
    obj = next((o for o in scope["objects"] if o.pk == _positive_id(baseline_item_id, "baselineItemId")), None)
    if obj is None:
        _fail("OBJECT_APPLICABILITY_OBJECT_OUT_OF_SCOPE", "对象不在计划固定的完整基线范围。")
    snapshot = _context(scope, obj)
    proofs = []
    for fact in EngineeringDerivedFact.objects.filter(calculation_id=scope["base"].pk, status="active").order_by("pk"):
        if (_trace_identity(fact.trace, "baselineItemId") == obj.pk
            and _trace_identity(fact.trace, "designItemId") == obj.design_item_id):
            proofs.append(_source_proof(scope, obj, fact.pk))
    return {"contractVersion": CONTRACT_VERSION, "context": snapshot, "contextHash": _hash(snapshot),
        "suggestedIdempotencyKey": "routing-object-applicability:v1:" + _hash(snapshot),
        "fullBaselineItemIds": sorted(o.pk for o in scope["objects"]),
        "fullDesignItemIds": sorted(o.design_item_id for o in scope["objects"]), "sourceProofs": proofs}


def _validate_basis(basis, scope, obj):
    if not isinstance(basis, dict) or basis.get("contractVersion") != BASIS_CONTRACT_VERSION:
        _fail("OBJECT_APPLICABILITY_BASIS_INVALID", "决定依据必须使用版本化结构化合同。")
    reference, source, rules, execution = (basis.get(k) for k in ("decisionReference", "sourceFact", "rules", "execution"))
    if (not isinstance(reference, dict)
        or any(not isinstance(reference.get(k), str) or not reference[k].strip() for k in ("code", "statement", "reference"))
        or not isinstance(source, dict) or not isinstance(rules, list) or not rules
        or execution != {"mode": "AUTHORIZED_CODEX_AGENT", "humanBusinessAcceptanceClaimed": False}):
        _fail("OBJECT_APPLICABILITY_BASIS_INVALID", "决定出处、正式事实、规则或执行方式不完整。")
    _hash_token(reference.get("referenceSha256"), "referenceSha256")
    proof = _source_proof(scope, obj, source.get("id"))
    if source.get("sourceSnapshotHash") != proof["sourceSnapshotHash"]:
        _fail("OBJECT_APPLICABILITY_SOURCE_HASH_DRIFT", "依据事实原生快照Hash已漂移。")
    seen = set()
    from .operation_requirement_service import _active
    for cited in rules:
        if not isinstance(cited, dict):
            _fail("OBJECT_APPLICABILITY_RULE_INVALID", "依据规则必须声明精确身份、版本及Hash。")
        pk = _positive_id(cited.get("id"), "ruleId")
        rule = EngineeringRuleDefinition.objects.filter(pk=pk, company_id=scope["company_id"]).first()
        if (pk in seen or not rule or rule.status != "released" or not _active(rule)
            or cited.get("version") != rule.version
            or cited.get("specificationHash") != specification_hash(rule.specification)):
            _fail("OBJECT_APPLICABILITY_RULE_INVALID", "依据规则未发布、失效、重复或版本Hash不一致。", ruleId=pk)
        seen.add(pk)
    return proof


def _payload(context, decision, basis, reason):
    return {"contractVersion": CONTRACT_VERSION, "context": context,
        "decision": decision, "basis": basis, "reason": reason}


def _fingerprint(context):
    return {"contractVersion": CONTRACT_VERSION, "context": context}


def _validate_record(record, scope):
    obj = next((o for o in scope["objects"] if o.pk == record.baseline_item_id), None)
    if obj is None:
        _fail("OBJECT_APPLICABILITY_OBJECT_OUT_OF_SCOPE", "已存决定对象不在当前完整计划范围。")
    context = _context(scope, obj)
    expected = {
        "company_id": scope["company_id"], "production_plan_id": scope["plan"].pk,
        "manufacturing_output_id": scope["output"].pk, "main_calculation_id": scope["base"].pk,
        "engineering_baseline_id": scope["baseline"].pk, "routing_version_id": scope["output"].routing_version_id,
        "routing_step_id": scope["step"].pk, "baseline_item_id": obj.pk, "design_item_id": obj.design_item_id,
        "source_record_id": scope["base"].source_record_id,
        "source_version": context["sourceVersion"], "source_content_hash": context["sourceContentHash"],
        "baseline_snapshot_hash": context["baselineSnapshotHash"], "object_content_hash": context["objectContentHash"],
        "calculation_input_hash": context["calculationInputHash"],
        "calculation_rule_graph_hash": context["calculationRuleGraphHash"],
        "calculation_result_hash": context["calculationResultHash"], "context_hash": _hash(context),
    }
    changed = [name for name, value in expected.items() if getattr(record, name) != value]
    if changed or record.decision not in DECISIONS or not isinstance(record.reason, str) or not record.reason.strip():
        _fail("OBJECT_APPLICABILITY_CONTEXT_DRIFT", "对象决定身份、内容Hash或决定合同不一致。", fields=changed)
    proof = _validate_basis(record.basis, scope, obj)
    ledger = record.write_request
    identity = ledger.source_identity
    # Reading the FK as a User object would SELECT credential columns. Only
    # these safe identity columns are needed by the native audit contract.
    actor = User.objects.filter(pk=record.created_by_id).values("id", "company_id", "username").first()
    if (not actor or actor["company_id"] != scope["company_id"]
        or ledger.organization_id != scope["company_id"] or ledger.action_code != ACTION
        or ledger.entity_type != ENTITY_TYPE
        or not isinstance(ledger.audit_metadata, dict)
        or ledger.audit_metadata.get("operatorId") != record.created_by_id
        or ledger.request_hash != _hash(_payload(context, record.decision, record.basis, record.reason))
        or identity.organization_id != scope["company_id"] or identity.source_system != "PCE_SYSTEM"
        or identity.source_type != "ROUTING_VERSION_CONTROLLED_CHANGE"
        or identity.source_object_type != SOURCE_OBJECT_TYPE
        or identity.external_id != "RoutingStepObject:" + record.context_hash
        or identity.target_entity_type != ENTITY_TYPE
        or identity.source_fingerprint != _hash(_fingerprint(context))
        or not isinstance(identity.audit_metadata, dict)
        or identity.audit_metadata.get("fingerprintPayload") != _fingerprint(context)):
        _fail("OBJECT_APPLICABILITY_LEDGER_INVALID", "对象决定办理人或原生请求绑定不一致。")
    return context, proof, actor


def validate_record_context(record):
    """Model clean guard; an initial RESERVED ledger and absent audit are legal.

    Committed ledger/audit proof is intentionally a separate readback check,
    because a native transaction creates the immutable row before its audit.
    """
    scope = _load_scope(record.production_plan_id, record.routing_step_id)
    return _validate_record(record, scope)[0]


def _result(record, audit_id, identity_id, source_proof):
    return {"recordId": record.pk, "contextHash": record.context_hash,
        "productionPlanId": record.production_plan_id, "manufacturingOutputId": record.manufacturing_output_id,
        "routingVersionId": record.routing_version_id, "routingStepId": record.routing_step_id,
        "baselineId": record.engineering_baseline_id, "baselineItemId": record.baseline_item_id,
        "designItemId": record.design_item_id, "decision": record.decision,
        "sourceFactId": source_proof["id"], "sourceSnapshotHash": source_proof["sourceSnapshotHash"],
        "auditId": audit_id, "writeRequestId": record.write_request_id, "sourceIdentityId": identity_id,
        "confirmedByUserId": record.created_by_id, "idempotentReplay": False}


def _committed_proof(record, scope):
    context, source, actor = _validate_record(record, scope)
    ledger, fingerprint = record.write_request, _fingerprint(context)
    identity = ledger.source_identity
    if (ledger.status != MasterDataWriteRequest.Status.COMMITTED or ledger.target_entity_id != str(record.pk)
        or ledger.audit_metadata.get("contractVersion") != CONTRACT_VERSION
        or identity.organization_id != scope["company_id"] or identity.source_system != "PCE_SYSTEM"
        or identity.source_type != "ROUTING_VERSION_CONTROLLED_CHANGE"
        or identity.source_object_type != SOURCE_OBJECT_TYPE
        or identity.external_id != "RoutingStepObject:" + record.context_hash
        or identity.target_entity_type != ENTITY_TYPE or identity.target_entity_id != str(record.pk)
        or identity.mapping_status != ExternalIdentity.MappingStatus.MATCH
        or identity.source_fingerprint != _hash(fingerprint)
        or identity.audit_metadata.get("contractVersion") != CONTRACT_VERSION
        or identity.audit_metadata.get("fingerprintPayload") != fingerprint):
        _fail("OBJECT_APPLICABILITY_COMMIT_INVALID", "对象决定缺少精确已提交请求及正式来源身份。")
    audits = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=scope["company_id"],
        action_code=ACTION, target_type=type(record).__name__, target_id=record.pk))
    if len(audits) != 1:
        _fail("OBJECT_APPLICABILITY_AUDIT_INVALID", "对象决定必须有唯一匹配的原生审计。")
    audit = audits[0]
    envelope = audit.after_snapshot if isinstance(audit.after_snapshot, dict) else {}
    expected_state = {"record": _snapshot(record), "context": context}
    chain = envelope.get("executionChain")
    authorization = envelope.get("authorization")
    from .routing_version_successor_service import ROUTING_PERMISSION
    if (audit.actor_id != record.created_by_id or audit.reason != record.reason[:300]
        or envelope.get("state") != expected_state or envelope.get("factSource") != "server"
        or audit.before_snapshot != {**envelope, "state": {}}
        or not isinstance(authorization, dict) or authorization.get("allowed") is not True
        or authorization.get("actionCode") != ROUTING_PERMISSION
        or not _organization_matches(authorization.get("organizationId"), scope["company_id"])
        or not isinstance(chain, dict) or chain.get("account") != actor["username"]
        or any(type(chain.get(k)) is not int or chain[k] <= 0 for k in
            ("employeeId", "positionId", "responsibilityId"))
        or envelope.get("importContext") != {"contractVersion": CONTRACT_VERSION,
            "contextHash": record.context_hash, "sourceFingerprint": _hash(fingerprint),
            "requestHash": ledger.request_hash}):
        _fail("OBJECT_APPLICABILITY_AUDIT_MISMATCH", "对象决定与原生审计的身份、办理链或来源快照不一致。")
    result = _result(record, audit.pk, identity.pk, source)
    if ledger.result != result:
        _fail("OBJECT_APPLICABILITY_COMMIT_INVALID", "对象决定与幂等提交结果不一致。")
    return result


@transaction.atomic
def confirm_group(user, production_plan_id, routing_step_id, contributions, reason):
    """Authorize once, validate every item, commit the group or roll it all back."""
    from .routing_version_successor_service import _authorize, _identity, _ledger
    scope = _load_scope(production_plan_id, routing_step_id, lock=True)
    organization_id, authorization, chain = _authorize(user, scope["output"].routing_version)
    if not isinstance(reason, str) or not reason.strip():
        _fail("OBJECT_APPLICABILITY_REASON_REQUIRED", "正式适用性决定必须提供办理说明。")
    reason = reason.strip()
    if not isinstance(contributions, list) or not contributions:
        _fail("OBJECT_APPLICABILITY_GROUP_REQUIRED", "必须提供非空对象决定组。")
    objects, seen, keys, prepared = {o.pk: o for o in scope["objects"]}, set(), set(), []
    existing = list(_model().objects.select_for_update().filter(
        production_plan_id=production_plan_id, routing_step_id=routing_step_id))
    for row in existing:
        _committed_proof(row, scope)
    for contribution in contributions:
        if not isinstance(contribution, dict) or set(contribution) != {
            "baselineItemId", "decision", "basis", "contextHash", "idempotencyKey"}:
            _fail("OBJECT_APPLICABILITY_PAYLOAD_INVALID", "对象决定必须提供精确合同字段。")
        obj_id = _positive_id(contribution["baselineItemId"], "baselineItemId")
        key = contribution["idempotencyKey"]
        if (obj_id in seen or obj_id not in objects or not isinstance(key, str)
            or not key.strip() or len(key) > 160 or key != key.strip() or key in keys
            or contribution["decision"] not in DECISIONS):
            _fail("OBJECT_APPLICABILITY_GROUP_INVALID", "对象越界、重复、决定无效或稳定幂等键无效。")
        seen.add(obj_id)
        keys.add(key)
        context = _context(scope, objects[obj_id])
        if contribution["contextHash"] != _hash(context):
            _fail("OBJECT_APPLICABILITY_CONTEXT_DRIFT", "待保存上下文Hash与当前正式范围不一致。")
        source = _validate_basis(contribution["basis"], scope, objects[obj_id])
        payload = _payload(context, contribution["decision"], deepcopy(contribution["basis"]), reason)
        matches = [row for row in existing if row.baseline_item_id == obj_id]
        if len(matches) > 1:
            _fail("OBJECT_APPLICABILITY_CONFLICT", "同一计划步骤对象存在冲突决定。")
        old = matches[0] if matches else None
        if old:
            old_result = _committed_proof(old, scope)
            if (old.write_request.idempotency_key != key or old.context_hash != _hash(context)
                or old.write_request.request_hash != _hash(payload)):
                _fail("OBJECT_APPLICABILITY_CONFLICT", "已存对象决定不可覆盖或换键建立别名。")
        else:
            old_result = None
            if MasterDataWriteRequest.objects.select_for_update().filter(
                organization_id=organization_id, action_code=ACTION, idempotency_key=key).exists():
                _fail("OBJECT_APPLICABILITY_CONFLICT", "幂等键已有请求但没有当前精确对象决定。")
        prepared.append((objects[obj_id], contribution, context, payload, source, old_result))
    results, created = [], 0
    for obj, contribution, context, payload, source, old_result in prepared:
        if old_result is not None:
            results.append({**old_result, "idempotentReplay": True})
            continue
        fingerprint_payload = _fingerprint(context)
        identity, fingerprint = _identity(organization_id=organization_id, object_type=SOURCE_OBJECT_TYPE,
            external_id="RoutingStepObject:" + _hash(context), target_type=ENTITY_TYPE,
            fingerprint_payload=fingerprint_payload)
        if (identity.target_entity_id or identity.mapping_status != ExternalIdentity.MappingStatus.CREATE
            or identity.source_fingerprint != fingerprint):
            _fail("OBJECT_APPLICABILITY_CONFLICT", "正式来源身份已有不同目标或指纹。")
        ledger = _ledger(organization_id=organization_id, action_code=ACTION, entity_type=ENTITY_TYPE,
            idempotency_key=contribution["idempotencyKey"], request_hash=_hash(payload), identity=identity, user=user)
        row = _model()(company_id=organization_id, production_plan=scope["plan"],
            manufacturing_output=scope["output"], main_calculation=scope["base"],
            engineering_baseline=scope["baseline"], routing_version=scope["output"].routing_version,
            routing_step=scope["step"], baseline_item=obj, design_item=obj.design_item,
            source_record=scope["base"].source_record, source_version=context["sourceVersion"],
            source_content_hash=context["sourceContentHash"], baseline_snapshot_hash=context["baselineSnapshotHash"],
            object_content_hash=context["objectContentHash"], calculation_input_hash=context["calculationInputHash"],
            calculation_rule_graph_hash=context["calculationRuleGraphHash"],
            calculation_result_hash=context["calculationResultHash"], context_hash=_hash(context),
            decision=contribution["decision"], basis=payload["basis"], reason=reason, created_by=user, write_request=ledger)
        row._object_applicability_creation_authorized = True
        row.save()
        audit = _audit(user=user, organization_id=organization_id, action_code=ACTION, instance=row,
            before={}, after={"record": _snapshot(row), "context": context}, reason=reason,
            authorization=authorization, execution_chain=chain,
            audit_context={"contractVersion": CONTRACT_VERSION, "contextHash": row.context_hash,
                "sourceFingerprint": fingerprint, "requestHash": ledger.request_hash})
        identity.target_entity_id, identity.mapping_status = str(row.pk), ExternalIdentity.MappingStatus.MATCH
        identity.audit_metadata = {"contractVersion": CONTRACT_VERSION, "fingerprintPayload": fingerprint_payload}
        identity.full_clean()
        identity.save()
        result = _result(row, audit.pk, identity.pk, source)
        ledger.status, ledger.target_entity_id, ledger.result = MasterDataWriteRequest.Status.COMMITTED, str(row.pk), result
        ledger.audit_metadata = {"operatorId": user.pk, "contractVersion": CONTRACT_VERSION}
        ledger.save(update_fields=("status", "target_entity_id", "result", "audit_metadata", "updated_at"))
        _committed_proof(row, scope)
        results.append(result)
        created += 1
    return {"contractVersion": CONTRACT_VERSION, "productionPlanId": production_plan_id,
        "routingStepId": routing_step_id, "createdCount": created, "replayedCount": len(results) - created,
        "objects": results, "objectApplicability": _resolve_scope(scope)}


def _pending_reason(exc, baseline_item_id=None):
    return {"code": getattr(exc, "code", "OBJECT_APPLICABILITY_CONTEXT_INVALID"),
        "message": getattr(exc, "message", str(exc)),
        **({"baselineItemId": baseline_item_id} if baseline_item_id is not None else {})}


def _resolve_scope(scope):
    rows = list(_model().objects.select_related("write_request__source_identity").filter(
        production_plan_id=scope["plan"].pk, routing_step_id=scope["step"].pk))
    if not rows:
        return None
    partition = {REQUIRED: [], NOT_APPLICABLE: [], PENDING: []}
    results, reasons = [], []
    by_id = {}
    for row in rows:
        by_id.setdefault(row.baseline_item_id, []).append(row)
    object_ids = {o.pk for o in scope["objects"]}
    extras = sorted(set(by_id) - object_ids)
    if extras:
        reasons.append({"code": "OBJECT_APPLICABILITY_SCOPE_DRIFT", "baselineItemIds": extras,
            "message": "已存决定对象越过当前完整范围。"})
    for obj in scope["objects"]:
        candidates = by_id.get(obj.pk, [])
        if len(candidates) != 1:
            partition[PENDING].append(obj)
            reasons.append({"code": "OBJECT_APPLICABILITY_MISSING" if not candidates else "OBJECT_APPLICABILITY_CONFLICT",
                "baselineItemId": obj.pk, "message": "当前对象缺少唯一已提交适用性决定。"})
            continue
        row = candidates[0]
        try:
            from .routing_object_applicability_correction_service import effective_for_root
            effective_decision, proof, effective_basis, effective_reason = effective_for_root(row, scope)
        except Exception as exc:
            if not (isinstance(exc, (ValidationError, ObjectDoesNotExist)) or hasattr(exc, "code")):
                raise
            partition[PENDING].append(obj)
            reasons.append(_pending_reason(exc, obj.pk))
        else:
            partition[effective_decision].append(obj)
            results.append({**proof, "basis": effective_basis, "reason": effective_reason})
    if extras:
        # A changed scope must never preserve an all-excluded aggregate.
        partition[PENDING] = list(scope["objects"])
        partition[REQUIRED], partition[NOT_APPLICABLE] = [], []
    complete = not partition[PENDING] and not extras
    result = PENDING if not complete else REQUIRED if partition[REQUIRED] else NOT_APPLICABLE
    return {"contractVersion": CONTRACT_VERSION, "factSource": "server",
        "scope": {"productionPlanId": scope["plan"].pk, "manufacturingOutputId": scope["output"].pk,
            "baselineId": scope["baseline"].pk}, "result": result, "complete": complete,
        "fullBaselineItemIds": sorted(o.pk for o in scope["objects"]),
        "fullDesignItemIds": sorted(o.design_item_id for o in scope["objects"]),
        "requiredBaselineItemIds": sorted(o.pk for o in partition[REQUIRED]),
        "requiredDesignItemIds": sorted(o.design_item_id for o in partition[REQUIRED]),
        "excludedBaselineItemIds": sorted(o.pk for o in partition[NOT_APPLICABLE]),
        "excludedDesignItemIds": sorted(o.design_item_id for o in partition[NOT_APPLICABLE]),
        "unknownBaselineItemIds": sorted(o.pk for o in partition[PENDING]),
        "unknownDesignItemIds": sorted(o.design_item_id for o in partition[PENDING]),
        "objects": results, "reasons": reasons}


@transaction.atomic
def resolve_for_step(step, production_plan=None, manufacturing_output=None, engineering_calculation=None,
                     order_engineering_instance=None, order_engineering_baseline=None, bom_version=None):
    """Return None without this exact plan/step's records; never cross plans."""
    if production_plan is None:
        return None
    plan_id = getattr(production_plan, "pk", production_plan)
    if not _model().objects.filter(production_plan_id=plan_id, routing_step_id=step.pk).exists():
        return None
    try:
        scope = _load_scope(plan_id, step.pk)
        supplied = ((manufacturing_output, scope["output"]), (engineering_calculation, scope["base"]),
            (order_engineering_instance, scope["base"].engineering_instance),
            (order_engineering_baseline, scope["baseline"]), (bom_version, scope["output"].bom_version))
        if (step.routing_version_id != scope["step"].routing_version_id
            or step.operation_id != scope["step"].operation_id
            or any(value is not None and getattr(value, "pk", value) != expected.pk for value, expected in supplied)):
            _fail("OBJECT_APPLICABILITY_CONTEXT_DRIFT", "消费者提供的Plan/Output/工程上下文不是同一固定正式组合。")
        return _resolve_scope(scope)
    except Exception as exc:
        if not (isinstance(exc, (ValidationError, ObjectDoesNotExist)) or hasattr(exc, "code")):
            raise
        # Keep the original failure visible and refuse to infer zero workload.
        return {"contractVersion": CONTRACT_VERSION, "factSource": "server", "result": PENDING,
            "complete": False, "scope": {"productionPlanId": plan_id,
                "manufacturingOutputId": getattr(manufacturing_output, "pk", manufacturing_output),
                "baselineId": getattr(order_engineering_baseline, "pk", order_engineering_baseline)},
            "fullBaselineItemIds": [], "fullDesignItemIds": [], "requiredBaselineItemIds": [],
            "requiredDesignItemIds": [], "excludedBaselineItemIds": [], "excludedDesignItemIds": [],
            "unknownBaselineItemIds": [], "unknownDesignItemIds": [], "objects": [],
            "reasons": [_pending_reason(exc)]}


class RoutingObjectApplicabilityService:
    """Public native facade shared by preparation and existing consumers."""

    build_context = staticmethod(build_context)
    confirm_group = staticmethod(confirm_group)
    resolve_for_step = staticmethod(resolve_for_step)
