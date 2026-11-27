"""Verified sales delivery evidence, stored with the existing order batches."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from .enterprise_authority import allowed
from .models import SalesOrder
from .read_scope import restrict_orders

DELIVERY_PERMISSION = "sales.order.delivery.start"
REGISTER_ACTION = "sales.order.delivery_evidence.register"
DOCUMENTS = {
    "customer_receipt": "客户签收单",
    "carrier_delivery": "承运人妥投凭证",
    "installation_acceptance": "安装验收单",
    "specified_dispatch": "合同约定发运凭证",
    "order_acceptance": "整单验收单",
}
DEFAULT_DOCUMENT = "customer_receipt"
RECORDABLE_STATES = {
    "approved", "confirmed", "engineering", "manufacturing_ready",
    "in_progress", "delivering", "completed",
}


def can_record_delivery(actor, order):
    if order.status not in RECORDABLE_STATES or order.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE:
        return False
    within_scope = (
        allowed(actor, DELIVERY_PERMISSION, (order.department_id,), owner_id=order.created_by_id, department_bound=True)
        and restrict_orders(SalesOrder.objects.filter(pk=order.pk), actor).exists()
        and AuthorizationService.decide(
            user=actor, action_code=DELIVERY_PERMISSION, organization_id=order.company_id,
            business_object={"organizationId": str(order.company_id), "departmentId": order.department_id,
                             "ownerUserId": order.created_by_id},
        )["allowed"]
    )
    if not within_scope:
        return False
    from .services import SalesBusinessError, _workflow_actor

    try:
        _workflow_actor(actor, DELIVERY_PERMISSION)
    except SalesBusinessError:
        return False
    return True


def order_delivery_info(order):
    return order.delivery_information if isinstance(order.delivery_information, dict) else {}


def delivery_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def business_today():
    return datetime.now(timezone.get_default_timezone()).date()


def delivery_batches(info):
    value = info.get("batches")
    return value if isinstance(value, list) else []


def verified_delivery_records(order, info):
    stored = [info.get("verifiedDeliveryPolicy"), info.get("verifiedOrderAcceptance"), *delivery_batches(info)]
    by_id = {record["deliveryAuditId"]: record for record in stored
             if isinstance(record, dict) and type(record.get("deliveryAuditId")) is int and 0 < record["deliveryAuditId"] < 2**63}
    if not by_id:
        return {}
    audits = OrganizationOperatingAuditRecord.objects.filter(
        pk__in=by_id, organization_id=order.company_id, target_type="SalesOrder",
        target_id=order.pk, action_code=REGISTER_ACTION,
    ).select_related("actor")
    verified = {}
    for entry in audits:
        record = by_id[entry.pk]
        body = {key: value for key, value in record.items() if key != "deliveryAuditId"}
        if entry.after_snapshot.get("deliveryEvidence") == body:
            verified[entry.pk] = {**record, "verifiedBy": entry.actor.real_name,
                                  "verifiedAt": entry.created_at.isoformat()}
    return verified


def _registered_batches(order, items, info, accepted):
    """Retain original rows, and classify each against the effective audited batch."""
    by_line = {item.line_no: item for item in items.values()}
    rows, unmatched, seen = [], [], set()
    for index, raw in enumerate(delivery_batches(info), 1):
        if not isinstance(raw, dict):
            continue
        item_id, line_no = raw.get("salesOrderItemId"), raw.get("lineNo")
        item_by_id = items.get(item_id) if type(item_id) is int else None
        item_by_line = by_line.get(line_no) if type(line_no) is int else None
        batch_no = str(raw.get("batchNo") or f"BATCH-{index}")
        item = item_by_id or item_by_line
        conflict = item_by_id and item_by_line and item_by_id.pk != item_by_line.pk
        if item is None or conflict:
            unmatched.append({"sourceIndex": index, "batchNo": batch_no, "salesOrderItemId": item_id,
                              "lineNo": line_no, "reason": "订单行稳定ID与行号指向不同明细" if conflict
                              else "未找到同一订单内匹配的有效明细"})
            continue
        key = str(raw.get("id") or batch_no)
        issues = ["交付批次标识重复"] if key in seen else []
        seen.add(key)
        unit = str(raw.get("uomCode") or (item.uom.code if item.uom_id else ""))
        if item.uom_id and unit != item.uom.code:
            issues.append("交付批次单位与订单行单位不一致")
        raw_qty = str(raw.get("quantity") or 0)
        try:
            qty = Decimal(raw_qty)
        except (InvalidOperation, ValueError):
            qty = Decimal("NaN")
        if not qty.is_finite() or qty <= 0:
            issues.append("交付批次数量无效")
        raw_date = str(raw.get("actualDeliveryDate") or "")
        audit_id = raw.get("deliveryAuditId")
        proof = accepted.get(audit_id) if type(audit_id) is int else None
        verified = bool(proof and all(raw.get(key) == value for key, value in proof.items()
                                      if key not in {"verifiedAt", "verifiedBy"}))
        rows.append({
            "id": raw.get("id") or f"delivery-{order.pk}-{index}", "batchNo": batch_no,
            "salesOrderItemId": item.pk, "lineNo": item.line_no, "quantity": raw_qty, "uomCode": unit,
            "customerRequiredDate": str(raw.get("customerRequiredDate") or item.required_date.isoformat()),
            "committedDeliveryDate": str(raw.get("committedDeliveryDate") or ""),
            "plannedCompletionDate": str(raw.get("plannedCompletionDate") or ""), "actualDeliveryDate": raw_date,
            "status": str(raw.get("status") or ("delivered" if raw_date else "planned")),
            "statusLabel": str(raw.get("statusLabel") or ("已交付" if raw_date else "待交付")),
            "associationStatus": "CONFLICT" if issues else "MATCHED", "associationIssues": issues,
            "verificationLabel": "归属或数量待核" if issues else "已核验" if verified else
                                 "历史登记（未核验）" if raw_date else "待交付",
            "deliveryAuditId": audit_id if verified else None,
            "sourceNo": proof["sourceNo"] if verified else None,
        })
    return rows, unmatched


def delivery_evidence_facts(order, items, records=None):
    info = order_delivery_info(order)
    if records is None:
        records = verified_delivery_records(order, info)
    source_policy = info.get("verifiedDeliveryPolicy")
    policy_id = source_policy.get("deliveryAuditId") if isinstance(source_policy, dict) else None
    policy = records.get(policy_id) if type(policy_id) is int else None
    if policy and (policy["recordKind"] != "policy" or policy["contractNo"] != order.contract_reference.strip()):
        policy = None
    document = policy["documentType"] if policy else DEFAULT_DOCUMENT
    needs_acceptance = bool(policy and policy["wholeOrderAcceptance"])
    today = business_today()
    valid_by_line = defaultdict(list)
    seen = set()
    item_by_id = {item.pk: item for item in items}
    for record in records.values():
        if record["recordKind"] != "batch" or record["documentType"] != document:
            continue
        item = item_by_id.get(record["salesOrderItemId"])
        day = delivery_date(record["actualDeliveryDate"])
        key = (record["sourceNo"], record["salesOrderItemId"])
        if (item is None or record["lineNo"] != item.line_no or not item.uom_id or record["uomCode"] != item.uom.code
                or day is None or day > today or day < order.order_date or key in seen):
            continue
        try:
            quantity = Decimal(record["quantity"])
        except (InvalidOperation, TypeError):
            continue
        if quantity.is_finite() and quantity > 0:
            seen.add(key)
            valid_by_line[item.pk].append((day, quantity, record))
    accepted = {batch["deliveryAuditId"]: batch for values in valid_by_line.values()
                for _, _, batch in values}
    registered, unmatched = _registered_batches(order, item_by_id, info, accepted)
    history_by_line = defaultdict(list)
    for batch in registered:
        if batch["verificationLabel"] == "历史登记（未核验）" and delivery_date(batch["actualDeliveryDate"]):
            history_by_line[batch["salesOrderItemId"]].append(batch)
    lines = []
    for item in item_by_id.values():
        confirmed = sorted(valid_by_line[item.pk], key=lambda entry: (entry[0], entry[2]["deliveryAuditId"]))
        total, sufficient_day = Decimal("0"), None
        for day, quantity, _ in confirmed:
            total += quantity
            if sufficient_day is None and total >= item.quantity:
                sufficient_day = day
        remaining = max(item.quantity - total, Decimal("0"))
        excess = max(total - item.quantity, Decimal("0"))
        history = history_by_line[item.pk]
        lines.append({
            "salesOrderItemId": item.pk, "lineNo": item.line_no, "materialName": item.material.name,
            "orderedQty": str(item.quantity), "deliveredQty": str(total),
            "uomLabel": item.uom.name if item.uom_id else "", "uomCode": item.uom.code if item.uom_id else "",
            "remainingQty": str(remaining), "overDeliveredQty": str(excess),
            "deliveryQuantityStatus": "OVER_DELIVERED" if excess else "PENDING" if remaining else "DELIVERED",
            "customerRequiredDate": item.required_date.isoformat(),
            "committedDeliveryDate": str(info.get("committedDeliveryDate") or ""),
            "historicalUnverifiedQty": str(sum((Decimal(batch["quantity"]) for batch in history), Decimal("0"))),
            "historicalBatches": history,
            "fulfilledDate": sufficient_day.isoformat() if sufficient_day else None,
            "batches": [record for _, _, record in confirmed],
        })
    full_dates = [line["fulfilledDate"] for line in lines]
    last_line = max(full_dates) if lines and all(full_dates) else None
    acceptance = info.get("verifiedOrderAcceptance")
    acceptance_id = acceptance.get("deliveryAuditId") if isinstance(acceptance, dict) else None
    acceptance = records.get(acceptance_id) if type(acceptance_id) is int else None
    if acceptance and (acceptance["recordKind"] != "acceptance" or not needs_acceptance
                       or acceptance["contractNo"] != policy["contractNo"]):
        acceptance = None
    if needs_acceptance:
        accepted_on = delivery_date(acceptance["businessDate"]) if acceptance else None
        actual = accepted_on if last_line and accepted_on and last_line <= accepted_on.isoformat() and accepted_on <= today else None
        source_label = "合同约定整单验收 · 整单验收单"
    else:
        actual = delivery_date(last_line)
        source_label = "各应交行首次足额日期中的最晚日"
    promised = delivery_date(info.get("committedDeliveryDate"))
    delay_days = max((actual - promised).days, 0) if actual and promised else None
    late = bool(delay_days)
    if actual and promised:
        label = "订单交付延期" if late else "订单按时交付"
        reason = "实际交付晚于承诺交期。" if late else "实际交付未晚于承诺交期。"
    else:
        label = "交付延期待核"
        prefix = "承诺交期已过，" if promised and promised < today else ""
        if not last_line:
            reason = prefix + ("缺少实际交付日期，各应交行尚未全部足额。" if seen
                               else "缺少实际交付日期。")
        elif needs_acceptance and not actual:
            reason = prefix + "各应交行已足额，缺少符合合同约定的整单验收日期。"
        else:
            reason = "缺少承诺交期。"
    return {
        "promisedDate": promised.isoformat() if promised else None,
        "actualDeliveryDate": actual.isoformat() if actual else None,
        "customerRequiredDate": order.required_delivery_date.isoformat(),
        "planSourceLabel": "销售订单交付信息 · 承诺交期", "actualSourceLabel": source_label,
        "isLate": late, "delayDays": delay_days, "statusLabel": label, "reason": reason,
        "batchDocumentType": document, "batchDocumentLabel": DOCUMENTS[document],
        "wholeOrderAcceptanceRequired": needs_acceptance, "allLinesFulfilledDate": last_line,
        "contractPolicy": policy, "orderAcceptance": acceptance, "lines": lines,
        "registeredBatches": registered, "unmatchedBatches": unmatched,
        "associationConflictCount": len(unmatched) + sum(bool(batch["associationIssues"]) for batch in registered),
    }