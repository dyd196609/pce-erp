"""Opt-in, append-only evidence for one audited engineering identity transition.

The approved commercial snapshot and original MAKE fact remain immutable.
"""
import json
import os
from django.core.exceptions import ObjectDoesNotExist
from system.models import OrganizationOperatingAuditRecord
from sales.models import SalesOrderItemSupplyAdmission
from .models import CRMOrderVersionCarryForward, OrderEngineeringInstance, OrderReviewSalesOrderRelation


def enabled():
    return os.environ.get("PCE_ENGINEERING_IDENTITY_CARRY_ENABLED") == "1"


def normalized(value):
    return json.loads(json.dumps(value, default=str))


def capture_basis(item, admission):
    from .crm_order_version_carry_forward import matching_proof
    from sales.supply_admission_service import supply_admission_facts
    relation = OrderReviewSalesOrderRelation.objects.select_related("sales_order").get(pk=admission.crm_order_relation_id)
    proof = matching_proof(relation)
    supply = supply_admission_facts(item)
    if not proof or supply.get("status") != "CONFIRMED" or supply.get("supplyBranch") != "MAKE":
        raise ValueError("工程身份受控承接需要有效商业版本证明及已确认MAKE事实。")
    if proof.validation_results.get("engineeringIdentityCarry"):
        raise ValueError("该订单已存在身份承接证明，请核定现有承接，不自动串接新转换。")
    return {"proof": proof, "supplyFactId": supply["factId"]}


def append_proof(*, item, instance, item_audit, admission, user, basis):
    from .crm_order_version_carry_forward import digest, order_snapshot
    previous = basis["proof"]
    snapshot = normalized(order_snapshot(item.sales_order))
    entry = {"previousProofId": previous.pk, "salesOrderItemId": item.pk,
        "oeiId": instance.pk, "authorizationId": admission.authorization_id,
        "itemAuditId": item_audit.pk, "supplyFactId": basis["supplyFactId"],
        "productCategoryId": instance.product_category_id, "processTypeId": instance.selected_process_type_id,
        "sourceRecordId": instance.source_record_id}
    validation = {**previous.validation_results, "engineeringIdentityCarry": [entry]}
    proof, _ = CRMOrderVersionCarryForward.objects.get_or_create(
        relation_id=previous.relation_id, target_version=item.sales_order.version,
        content_hash=digest(snapshot), defaults={
            "company_id": item.sales_order.company_id, "sales_order": item.sales_order,
            "original_version": previous.original_version, "content_snapshot": snapshot,
            "source_fingerprint": previous.source_fingerprint, "scope_fingerprint": previous.scope_fingerprint,
            "version_differences": [*previous.version_differences, {"action": "PDE_ENGINEERING_IDENTITY_CARRY", **entry}],
            "validation_results": validation, "approval_evidence": previous.approval_evidence,
            "created_by": user,
        })
    if validated_identity_proof(previous.relation, item) is None:
        raise ValueError("工程身份转换与商业快照、PDE授权或审计不一致，已回滚。")
    return proof


def validated_identity_proof(relation, item):
    """Validate exact evidence only; never mutate or repair historical facts."""
    if not enabled() or item.engineering_mode != "ORDER_ENGINEERED":
        return None
    from .crm_order_version_carry_forward import digest, order_snapshot
    from .production_foundation_service import _snapshot
    from .pde_engineering_preparation_admission import require_pde_engineering_preparation_admission, PDEEngineeringPreparationAdmissionError
    try:
        order = relation.sales_order
        if order.status != "approved" or order.pk != item.sales_order_id:
            return None
        snapshot = normalized(order_snapshot(order))
        proof = CRMOrderVersionCarryForward.objects.filter(relation=relation,
            company_id=order.company_id, sales_order=order, target_version=order.version,
            content_hash=digest(snapshot)).first()
        if not proof or proof.content_snapshot != snapshot or proof.source_fingerprint != relation.source_content_hash_snapshot:
            return None
        entries = proof.validation_results.get("engineeringIdentityCarry") or []
        if len(entries) != 1 or entries[0].get("salesOrderItemId") != item.pk:
            return None
        entry = entries[0]
        previous = CRMOrderVersionCarryForward.objects.get(pk=entry["previousProofId"],relation=relation,
            sales_order=order, target_version=order.version, company_id=order.company_id)
        if (previous.pk >= proof.pk or digest(previous.content_snapshot) != previous.content_hash
                or previous.source_fingerprint != proof.source_fingerprint
                or previous.scope_fingerprint != proof.scope_fingerprint
                or previous.approval_evidence != proof.approval_evidence
                or previous.original_version != relation.order_version_snapshot
                or proof.original_version != previous.original_version):
            return None
        old_snapshot = previous.content_snapshot
        expected = normalized(snapshot)
        old_line = next(x for x in old_snapshot["lines"] if x["id"] == item.pk)
        new_line = next(x for x in expected["lines"] if x["id"] == item.pk)
        if old_line["engineering_mode"] != "STANDARD" or not item.customer_product_name:
            return None
        for key in ("engineering_mode", "customer_product_name"):
            new_line[key] = old_line[key]
        if expected != old_snapshot:
            return None
        admission = require_pde_engineering_preparation_admission(company_id=order.company_id,sales_order_item_id=item.pk,authorization_id=entry["authorizationId"])
        if admission.crm_order_relation_id != relation.pk:
            return None
        instance = OrderEngineeringInstance.objects.get(pk=entry["oeiId"],sales_order_item=item,
            engineering_preparation_authorization_id=entry["authorizationId"])
        if (hasattr(instance, "admission_chain_revocation") or instance.company_id != order.company_id
                or instance.source_record_id != relation.review.source_record_id
                or not instance.product_category_id or not instance.selected_process_type_id
                or not instance.product_category.is_active or not instance.selected_process_type.is_active
                or entry.get("productCategoryId") != instance.product_category_id
                or entry.get("processTypeId") != instance.selected_process_type_id
                or entry.get("sourceRecordId") != instance.source_record_id):
            return None
        audit = OrganizationOperatingAuditRecord.objects.get(pk=entry["itemAuditId"],
            organization_id=order.company_id,target_type="SalesOrderItem",target_id=item.pk,
            action_code="production.engineering.order.maintain",actor_id=proof.created_by_id)
        before = audit.before_snapshot.get("state",{})
        after = audit.after_snapshot.get("state",{})
        if not audit.after_snapshot.get("authorization",{}).get("allowed") or after != normalized(_snapshot(item)):
            return None
        changed = {key for key in set(before)|set(after) if before.get(key)!=after.get(key)}
        if changed != {"engineering_mode","customer_product_name"} or before.get("engineering_mode")!="STANDARD" or before.get("customer_product_name") != old_line["customer_product_name"]:
            return None
        fact = SalesOrderItemSupplyAdmission.objects.get(pk=entry["supplyFactId"],sales_order_item=item,supply_type="MAKE")
        from sales.supply_admission_service import source_snapshot
        if {**fact.source_snapshot,"engineeringMode":"ORDER_ENGINEERED"} != source_snapshot(item):
            return None
        return proof
    except (ObjectDoesNotExist, KeyError, StopIteration, TypeError, ValueError, PDEEngineeringPreparationAdmissionError):
        return None


def supply_carry_proof(item, fact):
    if not enabled() or fact.supply_type != "MAKE":
        return None
    from .crm_order_version_carry_forward import matching_proof, CarryForwardError
    try:
        instances=list(OrderEngineeringInstance.objects.filter(sales_order_item=item).select_related(
            "engineering_preparation_authorization__predecessor_relation__crm_order_relation__sales_order")[:2])
        if len(instances)!=1 or not instances[0].engineering_preparation_authorization_id:
            return None
        relation=instances[0].engineering_preparation_authorization.predecessor_relation.crm_order_relation
        proof=matching_proof(relation)
        if proof and any(e.get("supplyFactId")==fact.pk for e in proof.validation_results.get("engineeringIdentityCarry",[])):
            return proof
    except (ObjectDoesNotExist,CarryForwardError):
        return None
    return None
