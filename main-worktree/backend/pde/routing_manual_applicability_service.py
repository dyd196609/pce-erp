"""Controlled order-engineering manual decisions for conditional routing steps.

The persisted business fact lives inside ``RoutingVersion.applicability``.  It
is intentionally scoped by the complete order-engineering identity rather than
by product/category name, so a decision can never leak to another order.  The
write path reuses the existing routing permission, formal executor chain,
idempotency ledger and organization audit.
"""
from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status
from .routing_read_context import memo_read

from copy import deepcopy
from hashlib import sha256
import json

from django.db import transaction
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import OrganizationOperatingAuditRecord

from .models import BOMVersion, OrderEngineeringBaseline, RoutingVersion
from .production_foundation_service import _audit, _snapshot
from .routing_version_successor_service import (
    RoutingVersionChangeError,
    _authorize,
    _canonical_hash,
    _identity,
    _ledger,
)


MANUAL_CONTRACT_VERSION = "PCE-ROUTING-MANUAL-APPLICABILITY-V1.0"
MANUAL_ACTION = "pde.routing_version.confirm_manual_step_applicability"
MANUAL_SOURCE_TYPE = "AUTHORIZED_BUSINESS_PERSON_MANUAL_CONFIRMATION"
MANUAL_SOURCE_LABEL = "授权业务人员人工确认"

DECISION_LABELS = {
    "YES": "是",
    "NO": "否",
    "PENDING": "待确认",
}


def _context_key(snapshot):
    return (
        f"OEI:{snapshot['orderEngineeringInstanceId']}|"
        f"BASELINE:{snapshot['orderEngineeringBaselineId']}|"
        f"CALC:{snapshot['engineeringCalculationId']}|"
        f"BOM:{snapshot['bomVersionId']}"
    )


def _baseline_for_calculation(calculation):
    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    reference = trace.get("baselineReference")
    baseline_id = reference.get("id") if isinstance(reference, dict) else None
    if not baseline_id or not calculation.sales_order_item_id:
        return None
    return production_baselines().filter(
        pk=baseline_id,
        company_id=calculation.company_id,
        sales_order_id=calculation.sales_order_item.sales_order_id,
        status="confirmed",
    ).first()


def _route_matches_instance(version, instance):
    routing = version.routing
    if routing.applicability_scope == "ORDER_ENGINEERING":
        return routing.order_engineering_instance_id == instance.pk
    if routing.applicability_scope == "PRODUCT_CATEGORY":
        return bool(
            routing.product_category_id == instance.product_category_id
            and routing.manufacturing_process_type_id == instance.selected_process_type_id
        )
    return bool(
        instance.product_id
        and routing.product_id == instance.product_id
        and version.product_version_id == instance.baseline_product_version_id
    )


def _snapshot_context(version, bom_version, baseline):
    calculation = bom_version.source_calculation
    instance = bom_version.order_engineering_instance
    order_item = calculation.sales_order_item
    order = order_item.sales_order
    snapshot = {
        "organizationId": version.routing.company_id,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "salesOrderItemId": order_item.pk,
        "salesOrderLineNo": order_item.line_no,
        "orderEngineeringInstanceId": instance.pk,
        "orderEngineeringInstanceNo": instance.instance_no,
        "orderEngineeringBaselineId": baseline.pk,
        "orderEngineeringBaselineNo": baseline.baseline_no,
        "engineeringCalculationId": calculation.pk,
        "engineeringCalculationNo": calculation.calculation_no,
        "engineeringCalculationRevision": calculation.revision,
        "bomVersionId": bom_version.pk,
        "bomVersionNo": bom_version.bom_version,
        "bomVersionRevision": bom_version.revision,
        "routingId": version.routing_id,
        "routingVersionId": version.pk,
        "routingVersionNo": version.routing_version,
        "routingVersionRevision": version.revision,
    }
    snapshot["contextKey"] = _context_key(snapshot)
    snapshot["identityHash"] = sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    return snapshot


@memo_read('routing_exact_contexts', lambda version: version.pk)
def exact_contexts_for_version(version):
    """Return only provably compatible order-engineering contexts."""
    if not version.routing_id:
        return []
    rows = BOMVersion.objects.filter(
        bom__company_id=version.routing.company_id,
        bom_scope="order_specific",
        status="released",
        order_engineering_instance__isnull=False,
        source_calculation__isnull=False,
        source_calculation__status="completed",
    ).select_related(
        "order_engineering_instance",
        "source_calculation",
        "source_calculation__sales_order_item",
        "source_calculation__sales_order_item__sales_order",
        "bom",
    ).order_by("pk")
    contexts = []
    for bom_version in rows:
        calculation = bom_version.source_calculation
        instance = bom_version.order_engineering_instance
        if (
            calculation.engineering_instance_id != instance.pk
            or calculation.sales_order_item_id != instance.sales_order_item_id
            or calculation.company_id != version.routing.company_id
            or not _route_matches_instance(version, instance)
        ):
            continue
        baseline = _baseline_for_calculation(calculation)
        if baseline is None:
            continue
        contexts.append({
            "snapshot": _snapshot_context(version, bom_version, baseline),
            "bomVersion": bom_version,
            "engineeringCalculation": calculation,
            "orderEngineeringInstance": instance,
            "orderEngineeringBaseline": baseline,
        })
    return contexts


def _stored_contract(version):
    applicability = version.applicability if isinstance(version.applicability, dict) else {}
    value = applicability.get("manualStepApplicability")
    return value if isinstance(value, dict) else {}


def _decision_readback(version, context_snapshot, condition_code):
    contract = _stored_contract(version)
    if contract and contract.get("contractVersion") != MANUAL_CONTRACT_VERSION:
        return {
            "status": "INVALID",
            "pendingCode": "MANUAL_DECISION_CONTRACT_INVALID",
            "pendingReason": "人工判断合同版本无法识别。",
        }
    contexts = contract.get("contexts") if isinstance(contract.get("contexts"), dict) else {}
    stored_context = contexts.get(context_snapshot["contextKey"])
    if not isinstance(stored_context, dict):
        return {"status": "MISSING"}
    stored_snapshot = stored_context.get("context")
    if not isinstance(stored_snapshot, dict) or stored_snapshot != context_snapshot:
        return {
            "status": "INVALID",
            "pendingCode": "MANUAL_DECISION_IDENTITY_DRIFT",
            "pendingReason": "人工判断绑定的订单工程身份与当前正式事实不一致。",
        }
    decisions = stored_context.get("decisions")
    decision = decisions.get(condition_code) if isinstance(decisions, dict) else None
    if not isinstance(decision, dict):
        return {"status": "MISSING"}
    value = decision.get("decision")
    if value not in DECISION_LABELS:
        return {
            "status": "INVALID",
            "pendingCode": "MANUAL_DECISION_VALUE_INVALID",
            "pendingReason": "人工判断值不属于是、否或待确认。",
        }
    audit_id = decision.get("auditId")
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=audit_id,
        organization_id=context_snapshot["organizationId"],
        action_code=MANUAL_ACTION,
        target_type="RoutingVersion",
        target_id=version.pk,
        actor_id=decision.get("confirmedByUserId"),
    ).first()
    if audit is None:
        return {
            "status": "INVALID",
            "pendingCode": "MANUAL_DECISION_AUDIT_INVALID",
            "pendingReason": "人工判断缺少一致的正式审计事实。",
        }
    audited_state = (
        audit.after_snapshot.get("state")
        if isinstance(audit.after_snapshot, dict) else None
    )
    audited_decision = (
        audited_state.get("manualDecision")
        if isinstance(audited_state, dict) else None
    )
    audited_context = (
        audited_state.get("manualDecisionContext")
        if isinstance(audited_state, dict) else None
    )
    if (
        not isinstance(audited_decision, dict)
        or audited_decision.get("decision") != value
        or audited_decision.get("note") != (decision.get("note") or "")
        or audited_context != context_snapshot
        or audited_state.get("conditionCode") != condition_code
    ):
        return {
            "status": "INVALID",
            "pendingCode": "MANUAL_DECISION_AUDIT_MISMATCH",
            "pendingReason": "人工判断与正式审计快照不一致。",
        }
    return {
        "status": "PENDING" if value == "PENDING" else "RESOLVED",
        "decision": value,
        "decisionLabel": DECISION_LABELS[value],
        "result": "REQUIRED" if value == "YES" else "NOT_APPLICABLE" if value == "NO" else "PENDING",
        "note": decision.get("note") or "",
        "confirmedByUserId": decision.get("confirmedByUserId"),
        "confirmedByUsername": decision.get("confirmedByUsername") or "",
        "confirmedByEmployeeId": decision.get("confirmedByEmployeeId"),
        "confirmedAt": decision.get("confirmedAt") or "",
        "auditId": audit.pk,
        "writeRequestId": decision.get("writeRequestId"),
        "sourceType": MANUAL_SOURCE_TYPE,
        "sourceLabel": MANUAL_SOURCE_LABEL,
        "decisionRevision": decision.get("decisionRevision"),
    }


class RoutingManualApplicabilityService:
    @classmethod
    def readback(cls, version):
        contexts = []
        conditional_steps = [
            step for step in version.steps.select_related("operation").order_by("sequence", "pk")
            if isinstance(step.operation_parameters, dict)
            and isinstance(step.operation_parameters.get("applicability"), dict)
            and step.operation_parameters["applicability"].get("mode") == "CONDITIONAL"
        ]
        for item in exact_contexts_for_version(version):
            context = item["snapshot"]
            decisions = []
            for step in conditional_steps:
                condition_code = step.operation_parameters["applicability"].get("conditionCode") or ""
                current = _decision_readback(version, context, condition_code)
                decisions.append({
                    "stepId": step.pk,
                    "sequence": step.sequence,
                    "operationCode": step.operation.code,
                    "operationName": step.operation.name,
                    "conditionCode": condition_code,
                    "question": (
                        "本次订单工程对象是否需要雕刻纹路？"
                        if condition_code == "DRAWING_ENGRAVING_REQUIRED" else
                        "本次订单工程对象是否需要生产前异形加工？"
                    ),
                    "boundaryNote": (
                        "由正式授权业务人员判断；不要求上传图纸。"
                        if condition_code == "DRAWING_ENGRAVING_REQUIRED" else
                        "仅判断生产前异形加工；生产过程返工不包含在本项内。"
                    ),
                    "current": current,
                })
            contexts.append({"context": context, "decisions": decisions})
        return {
            "contractVersion": MANUAL_CONTRACT_VERSION,
            "sourceType": MANUAL_SOURCE_TYPE,
            "sourceLabel": MANUAL_SOURCE_LABEL,
            "decisionOptions": [
                {"value": value, "label": label} for value, label in DECISION_LABELS.items()
            ],
            "contexts": contexts,
            "contextCount": len(contexts),
            "conditionalDecisionCount": sum(len(row["decisions"]) for row in contexts),
        }

    @classmethod
    def resolve_for_step(
        cls, step, *, engineering_calculation=None, order_engineering_instance=None,
        order_engineering_baseline=None, bom_version=None,
    ):
        contexts = exact_contexts_for_version(step.routing_version)
        supplied = {
            "engineeringCalculationId": getattr(engineering_calculation, "pk", None),
            "orderEngineeringInstanceId": getattr(order_engineering_instance, "pk", None),
            "orderEngineeringBaselineId": getattr(order_engineering_baseline, "pk", None),
            "bomVersionId": getattr(bom_version, "pk", None),
        }
        supplied = {key: value for key, value in supplied.items() if value is not None}
        matches = [
            row for row in contexts
            if all(row["snapshot"].get(key) == value for key, value in supplied.items())
        ]
        if not supplied and len(contexts) == 1:
            matches = contexts
        if len(matches) > 1:
            return {
                "status": "INVALID",
                "pendingCode": "MANUAL_DECISION_CONTEXT_NOT_UNIQUE",
                "pendingReason": "存在多个订单工程对象，无法唯一读取人工判断。",
            }
        if not matches:
            return {"status": "MISSING"}
        parameters = step.operation_parameters if isinstance(step.operation_parameters, dict) else {}
        contract = parameters.get("applicability") if isinstance(parameters.get("applicability"), dict) else {}
        return _decision_readback(
            step.routing_version, matches[0]["snapshot"], contract.get("conditionCode") or "",
        )

    @classmethod
    @transaction.atomic
    def confirm(
        cls, *, version_id, user, context_key, condition_code, decision, note,
        idempotency_key, expected_audit_id=None,
    ):
        raise RoutingVersionChangeError('ORDER_EXECUTION_ARRANGEMENT_REQUIRED','订单工序执行判断请通过独立订单安排服务办理，不得新增路线或物料清单版本。')

