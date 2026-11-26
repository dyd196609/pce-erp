"""Version carry-forward evidence for an unchanged CRM identity and audited order changes."""

from hashlib import sha256
import json
import os
from django.db import transaction, connection, OperationalError
from time import sleep
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import ApprovalDecision
from .models import CRMOrderVersionCarryForward, OrderReviewSalesOrderRelation


class CarryForwardError(ValueError):
    pass


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def order_snapshot(order):
    fields = ("company_id", "customer_id", "department_id", "project_reference",
              "contract_reference", "external_source_no", "currency", "order_date",
              "required_delivery_date", "delivery_information", "version", "status")
    line_fields = ("id", "line_no", "material_id", "uom_id", "quantity", "unit_price",
                   "tax_rate", "price_tax_mode", "required_date", "engineering_mode",
                   "product_definition_id", "product_version_id", "customer_product_name",
                   "specification", "engineering_requirements", "quality_requirements")
    return {
        "header": {field: str(getattr(order, field)) for field in fields},
        "lines": list(order.items.order_by("line_no", "pk").values(*line_fields)),
    }


def checked_basis(relation):
    from .crm_order_admission import current_crm_sales_order_admission_facts

    order = relation.sales_order
    if order.status != "approved":
        raise CarryForwardError("订单须已批准后才能承接版本。")
    facts = current_crm_sales_order_admission_facts(order)
    if not facts.get("admitted") or facts.get("relationId") != relation.pk:
        raise CarryForwardError("当前来源或订单行范围未通过正式准入。")
    audits = list(OrganizationOperatingAuditRecord.objects.filter(
        target_type="SalesOrder", target_id=order.pk, organization_id=order.company_id,
        action_code__in=("sales.order.create", "sales.order.update", "sales.order.submit", "sales.order.approve"),
    ).order_by("pk"))
    if not audits or audits[0].action_code != "sales.order.create":
        raise CarryForwardError("缺少订单建档审计。")
    decision = ApprovalDecision.objects.filter(
        task__workflow_instance__document_type="SalesOrder",
        task__workflow_instance__document_id=order.pk, decision="approved",
        task__status="approved", task__workflow_instance__status="approved",
    ).order_by("-pk").first()
    if not decision or not audits or audits[-1].action_code != "sales.order.approve":
        raise CarryForwardError("缺少当前有效批准或完整审计链。")
    if audits[-1].actor_id != decision.actor_id:
        raise CarryForwardError("批准审计与决定的办理人不一致。")
    before = audits[-1].before_snapshot.get("state", {})
    if before.get("version") != order.version - 1:
        raise CarryForwardError("当前订单版本不在批准审计覆盖范围。")
    creation = audits[0].after_snapshot.get("state", {})
    expected_version = relation.order_version_snapshot
    expected_status = "draft"
    for audit in audits[1:]:
        prior = audit.before_snapshot.get("state", {})
        after = audit.after_snapshot.get("state", {})
        if audit.action_code == "sales.order.update":
            if expected_status != "draft" or after.get("version") != expected_version + 1:
                raise CarryForwardError("修改审计版本链不完整。")
        else:
            transition = {"sales.order.submit": ("draft", "submitted"),
                          "sales.order.approve": ("submitted", "approved")}[audit.action_code]
            if (expected_status != transition[0] or prior.get("status") != transition[0]
                    or after.get("status") != transition[1] or prior.get("version") != expected_version):
                raise CarryForwardError("提交、批准审计链不完整。")
            expected_status = transition[1]
        expected_version += 1
    if expected_version != order.version or expected_status != order.status:
        raise CarryForwardError("审计链未覆盖当前版本及状态。")
    header_fields = {"customerCode": order.customer.code, "orderDate": str(order.order_date),
        "currency": order.currency, "projectReference": order.project_reference,
        "contractReference": order.contract_reference, "externalSourceNo": order.external_source_no,
        "deliveryInformation": order.delivery_information, "requiredDate": str(order.required_delivery_date)}
    if any(creation.get(key) != value for key, value in header_fields.items()):
        raise CarryForwardError("当前订单内容与建档依据不一致，不能自动承接。")
    original_lines = creation.get("items", [])
    current = list(order.items.order_by("line_no", "pk"))
    if len(original_lines) != len(current):
        raise CarryForwardError("订单行范围已变化。")
    updates = [a.after_snapshot.get("state", {}) for a in audits if a.action_code == "sales.order.update"]
    for original, line in zip(original_lines, current):
        expected_tax = original.get("taxRate")
        for update in updates:
            if update.get("salesOrderItemId") == line.pk:
                expected_tax = update.get("taxRate", expected_tax)
        line_fields = {"uomId": line.uom_id, "engineeringMode": line.engineering_mode,
            "productDefinitionId": line.product_definition_id, "productVersionId": line.product_version_id,
            "priceTaxMode": line.price_tax_mode, "customerProductName": line.customer_product_name,
            "specification": line.specification, "engineeringRequirements": line.engineering_requirements,
            "qualityRequirements": line.quality_requirements}
        if any(original.get(key) != value for key, value in line_fields.items()):
            from .order_engineering_identity_carry import validated_identity_proof
            if validated_identity_proof(relation, line) is None:
                raise CarryForwardError("订单行工程内容或单位已变化。")
        from decimal import Decimal
        if (original.get("salesOrderItemId") != line.pk
                or original.get("materialCode") != line.material.code
                or Decimal(original["quantity"]) != line.quantity
                or Decimal(original["unitPrice"]) != line.unit_price
                or expected_tax is None or Decimal(expected_tax) != line.tax_rate):
            raise CarryForwardError("当前明细无法由审计链完整复核。")
    return order_snapshot(order), facts, audits, decision


def enabled():
    return os.environ.get("PCE_CRM_VERSION_CARRY_ENABLED") == "1"


def matching_proof(relation):
    if not enabled():
        return None
    from .order_lifecycle_source_projection import approved_source_relation
    relation = approved_source_relation(relation)
    snapshot, _, _, _ = checked_basis(relation)
    return CRMOrderVersionCarryForward.objects.filter(
        relation=relation, target_version=relation.sales_order.version,
        content_hash=digest(snapshot),
    ).first()


@transaction.atomic
def _prepare_proof(*, user, relation_id, sales_order_id):
    from .order_demand_preparation_service import _authorization
    _authorization(user)
    if not enabled():
        raise CarryForwardError("当前实例未启用关系版本受控承接。")
    relation = OrderReviewSalesOrderRelation.objects.select_for_update().select_related(
        "sales_order", "review__source_record",
    ).get(pk=relation_id, sales_order_id=sales_order_id, company_id=user.company_id)
    order = relation.sales_order
    if relation.order_version_snapshot == order.version:
        return None
    snapshot, facts, audits, decision = checked_basis(relation)
    proof, _ = CRMOrderVersionCarryForward.objects.get_or_create(
        relation=relation, target_version=order.version, content_hash=digest(snapshot),
        defaults={
            "company_id": order.company_id, "sales_order": order,
            "original_version": relation.order_version_snapshot,
            "content_snapshot": json.loads(json.dumps(snapshot, default=str)),
            "source_fingerprint": relation.source_content_hash_snapshot,
            "scope_fingerprint": digest(facts["businessIdentity"]),
            "version_differences": [{"auditId": a.pk, "action": a.action_code,
                "before": a.before_snapshot, "after": a.after_snapshot} for a in audits],
            "validation_results": facts["businessIdentity"],
            "approval_evidence": {"approvalDecisionId": decision.pk,
                "workflowInstanceId": decision.task.workflow_instance_id,
                "auditIds": [a.pk for a in audits]},
            "created_by": user,
        },
    )
    return proof


def prepare_proof(**kwargs):
    """Retry a complete rolled-back SQLite transaction; never retry partial writes."""
    nested = connection.in_atomic_block
    for attempt in range(20):
        try:
            return _prepare_proof(**kwargs)
        except OperationalError as error:
            if connection.vendor != "sqlite" or not any(x in str(error).lower() for x in ("locked", "busy")):
                raise
            if nested or attempt == 19:
                raise CarryForwardError("订单承接正在处理中，请刷新后重试。") from error
            sleep(0.05)
