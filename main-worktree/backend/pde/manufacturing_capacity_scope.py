"""Prove a versioned capacity usage scope from the existing formal write chain.

This is a read-only contract over StandardCapacity, its committed master-data
request, source identity and real audit. A JSON label alone is never authority
to remove a capacity from an existing APS source contract.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

from masterdata.models import MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord


CONTRACT = "PCE-MANUFACTURING-CAPACITY-SCOPE-V1"
ENGINEERING_EOR_ONLY = "ENGINEERING_EOR_ONLY"
ERROR = "MANUFACTURING_CAPACITY_SCOPE_INVALID"
SCOPE_FIELDS = {"contractVersion", "usageScope", "version", "businessFactReference", "sourceFingerprint"}


def _fail(message):
    # The EOR service also imports the manufacturing gate; defer this import.
    from .operation_requirement_service import OperationRequirementError
    raise OperationRequirementError(ERROR, message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":"))


def _physical_state(capacity):
    state = {"id": capacity.pk}
    for field in capacity._meta.concrete_fields:
        if field.attname == "updated_at":
            continue
        value = getattr(capacity, field.attname)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        state[field.attname] = value
    return state


def _state_matches(state, physical):
    if not isinstance(state, dict) or any(key not in state for key in physical):
        return False
    try:
        return _json({key: state[key] for key in physical}) == _json(physical)
    except (TypeError, ValueError):
        return False


def validate_capacity_usage_scope(scope):
    """Validate the data declaration without treating it as persisted proof."""
    if (not isinstance(scope, dict) or set(scope) != SCOPE_FIELDS
            or scope.get("contractVersion") != CONTRACT
            or scope.get("usageScope") != ENGINEERING_EOR_ONLY
            or any(not isinstance(scope.get(key), str) or not scope[key].strip()
                   or scope[key] != scope[key].strip()
                   for key in ("version", "businessFactReference", "sourceFingerprint"))
            or re.fullmatch(r"[0-9a-fA-F]{64}", scope.get("sourceFingerprint", "")) is None):
        _fail("产能用途域必须为精确的版本化EOR专用合同。")
    return scope


def capacity_usage_scope_proof(capacity, *, read_cache=None):
    """Return a persisted scope proof, None for the unchanged legacy contract.

    A declared but malformed, mixed, uncommitted or changed scope fails closed.
    Only an audited positive measured daily capacity may be EOR-only. No unit
    conversion, daily quantity, process identity or business field is inferred.
    """
    conditions = capacity.conditions if isinstance(capacity.conditions, dict) else {}
    if "capacityUsageScope" not in conditions:
        return None
    scope = validate_capacity_usage_scope(conditions["capacityUsageScope"])
    if "apsSourceRules" in conditions:
        _fail("EOR专用产能不得混用APS来源合同。")
    try:
        quantity = Decimal(str(capacity.quantity))
        basis = Decimal(str(capacity.time_basis_quantity))
    except (InvalidOperation, TypeError, ValueError):
        _fail("EOR专用产能必须保存正式正日产能及1天基准。")
    if (not quantity.is_finite() or quantity <= 0 or not basis.is_finite()
            or capacity.measurement_status != "measured"
            or capacity.time_basis != "day" or basis != Decimal(1)
            or capacity.time_unit != "DAY" or not capacity.pk
            or not capacity.company_id or not capacity.product_type_id
            or not capacity.operation_id or not capacity.work_center_id
            or not capacity.uom_id or not capacity.effective_from):
        _fail("EOR专用产能必须为有正式公司、类型、资源、单位与生效日期的正日产能。")
    operation, center, product_type, uom = (
        capacity.operation, capacity.work_center, capacity.product_type, capacity.uom,
    )
    if (any(row.company_id != capacity.company_id for row in (operation, center, product_type, uom))
            or any(not row.is_active for row in (operation, center, product_type, uom))
            or operation.calculation_uom_id != capacity.uom_id
            or operation.calculation_basis != uom.dimension
            or (operation.workshop_id and center.workshop_id != operation.workshop_id)
            or product_type.product_category.company_id != capacity.company_id
            or product_type.manufacturing_process_type.company_id != capacity.company_id):
        _fail("EOR专用产能必须引用同公司有效资源、产品类型和精确工序单位，且工作中心车间必须匹配。")
    physical = _physical_state(capacity)
    from .operation_requirement_service import _requirement_read_cache, _read_once, _today
    cache = _requirement_read_cache(read_cache, capacity.company_id)
    raw_key = (CONTRACT, 'raw', capacity.company_id, cache.user_id, _today(),
        capacity.__class__.__name__, capacity.pk) if cache is not None else ()
    ledgers = _read_once(cache, (*raw_key, 'ledgers', 'standard-capacities',
        'production.master_data.create', MasterDataWriteRequest.Status.COMMITTED, str(capacity.pk)),
        lambda: list(MasterDataWriteRequest.objects.filter(
        organization_id=capacity.company_id, entity_type="standard-capacities",
        action_code="production.master_data.create",
        status=MasterDataWriteRequest.Status.COMMITTED,
        target_entity_id=str(capacity.pk),
    ).select_related("source_identity").order_by("pk")))
    for ledger in ledgers:
        identity, result = ledger.source_identity, ledger.result
        if (ledger.organization_id != capacity.company_id or ledger.entity_type != 'standard-capacities'
                or ledger.action_code != 'production.master_data.create'
                or ledger.status != MasterDataWriteRequest.Status.COMMITTED
                or ledger.target_entity_id != str(capacity.pk)
                or identity.organization_id != capacity.company_id
                or identity.target_entity_type != "standard-capacities"
                or identity.target_entity_id != str(capacity.pk)
                or identity.mapping_status != "MATCH"
                or identity.source_fingerprint != scope["sourceFingerprint"]
                or not isinstance(identity.audit_metadata, dict)
                or identity.audit_metadata.get("capacityUsageScope") != scope
                or not isinstance(result, dict)
                or result.get("sourceIdentityId") != identity.pk
                or result.get("actionRequestId") != ledger.pk
                or not _state_matches(result.get("row"), physical)
                or type(result.get("auditId")) is not int
                or re.fullmatch(r"[0-9a-fA-F]{64}", ledger.request_hash) is None):
            continue
        audit = _read_once(cache, (*raw_key, 'audit', result['auditId'],
            'production.master_data.capacity.maintain', capacity.__class__.__name__, capacity.pk),
            lambda: OrganizationOperatingAuditRecord.objects.select_related("actor").defer("actor__password").filter(
            pk=result["auditId"], organization_id=capacity.company_id,
            action_code="production.master_data.capacity.maintain",
            target_type=capacity.__class__.__name__, target_id=capacity.pk,
        ).first())
        if (not audit or audit.pk != result['auditId'] or audit.organization_id != capacity.company_id
                or audit.action_code != 'production.master_data.capacity.maintain'
                or audit.target_type != capacity.__class__.__name__ or audit.target_id != capacity.pk
                or not isinstance(audit.after_snapshot, dict)):
            continue
        after, before = audit.after_snapshot, audit.before_snapshot
        authorization, chain = after.get("authorization"), after.get("executionChain")
        context = after.get("importContext")
        if (not isinstance(authorization, dict) or authorization.get("allowed") is not True
                or authorization.get("actionCode") != audit.action_code
                or str(authorization.get("organizationId")) != str(capacity.company_id)
                or not isinstance(chain, dict) or chain.get("account") != audit.actor.username
                or any(type(chain.get(key)) is not int or chain[key] <= 0
                       for key in ("employeeId", "positionId", "responsibilityId"))
                or audit.actor.company_id != capacity.company_id
                or not isinstance(ledger.audit_metadata, dict)
                or ledger.audit_metadata.get("operatorId") != audit.actor_id
                or result.get("executionChain") != chain
                or result.get("authorization") != authorization
                or not isinstance(context, dict) or context.get("capacityUsageScope") != scope
                or not isinstance(before, dict) or before.get("state") != {}
                or after.get("factSource") != "server"
                or not _state_matches(after.get("state"), physical)):
            continue
        return {
            **deepcopy(scope), "standardCapacityId": capacity.pk,
            "writeRequestId": ledger.pk, "sourceIdentityId": identity.pk,
            "auditId": audit.pk, "actorId": audit.actor_id,
            "capacitySnapshotHash": sha256(_json(physical).encode("utf-8")).hexdigest(),
        }
    _fail("产能用途域缺少同公司、同对象、同来源Hash的已提交正式写入与完整授权审计，或产能已变化。")
