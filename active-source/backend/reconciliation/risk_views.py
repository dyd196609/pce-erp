from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import DatabaseError, transaction
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from procurement.inventory_facts_api import (
    INVENTORY_READ_PERMISSION, INVENTORY_TRANSACTION_READ_PERMISSION,
    PAYABLE_CHECK_READ_PERMISSION, PURCHASE_INSPECTION_READ_PERMISSION,
    PURCHASE_RECEIPT_READ_PERMISSION,
)
from procurement.material_stock_authority import quality_projection
from procurement.models import PurchaseOrder, PurchaseReceipt, WarehouseInbound
from sales.enterprise_authority import (
    RISK_CHECK, RISK_CLOSE, RISK_HANDLERS, RISK_RECEIVE, allowed, audit, audit_row, history,
)
from sales.followup_views import EnterpriseView, conflict, read_failure, response, validated
from system.authorization import AuthorizationService
from system.models import User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object

from .models import PayableCheckAuthorityRecord, PurchaseReconciliation, PurchaseReconciliationDifference
from .risk_models import ProcurementEvidenceRisk


ACTIONS = {
    "receive": ("reconciliation.evidence_risk.receive", "受理并指定处理人"),
    "process": ("reconciliation.evidence_risk.process", "提交处置证据"),
    "close": ("reconciliation.evidence_risk.close", "独立复核并关闭"),
}
CATEGORIES = {
    "PRC_QUALITY_RELEASE_DIFFERENCE": "quality",
    "PRC_AMOUNT_DIFFERENCE": "payable", "PRC_CURRENCY_DIFFERENCE": "payable",
    "PRC_SUPPLIER_DIFFERENCE": "procurement", "PRC_QUANTITY_DIFFERENCE": "inventory",
}
TRANSITIONS = {("received", "processed"), ("processed", "closed")}


class ReceiveInput(serializers.Serializer):
    differenceId = serializers.IntegerField(min_value=1)
    handlerId = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300)


class UpdateInput(serializers.Serializer):
    expectedVersion = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300)
    evidence = serializers.CharField(max_length=1800)


def can_read_source(actor, code):
    return AuthorizationService.decide(user=actor, action_code=code)["allowed"]


def quantity_rows(documents):
    totals = defaultdict(Decimal)
    for document in documents:
        items = document.items
        if not isinstance(items, list) or not items:
            return None
        try:
            total = Decimal(0)
            for item in items:
                line, material, unit = item["purchaseOrderItemId"], item["materialId"], item["unit"]
                amount = Decimal(str(item["quantity"]))
                if not isinstance(line, int) or not isinstance(material, int) or not unit or not amount.is_finite() or amount <= 0:
                    return None
                totals[(line, material, unit)] += amount
                total += amount
            if total != document.quantity:
                return None
        except (KeyError, TypeError, InvalidOperation):
            return None
    return totals


def compare_quantities(order, receipts, inbounds):
    receipt_totals, inbound_totals = quantity_rows(receipts), quantity_rows(inbounds)
    if not receipt_totals or not inbound_totals or receipt_totals.keys() != inbound_totals.keys():
        return {"statusLabel": "待核", "rows": [], "reason": "缺少可按同一采购行、物料和单位核对的正式数量。"}
    order_lines = set(order.items.values_list("pk", "material_id"))
    if any((line, material) not in order_lines for line, material, _ in receipt_totals):
        return {"statusLabel": "待核", "rows": [], "reason": "收货与入库的采购行归属未核明。"}
    rows = [{"purchaseLineId": line, "unit": unit,
        "received": format(receipt_totals[(line, material, unit)].normalize(), "f"),
        "inbound": format(inbound_totals[(line, material, unit)].normalize(), "f")}
        for line, material, unit in sorted(receipt_totals)]
    return {"statusLabel": "数量一致" if receipt_totals == inbound_totals else "数量不一致",
        "rows": rows, "receiptNos": [x.receipt_no for x in receipts], "inboundNos": [x.inbound_no for x in inbounds]}


def source_checks(actor, order):
    checks = {"quantity": {"statusLabel": "无权读取", "rows": []},
        "quality": {"statusLabel": "无权读取"}, "payable": {"statusLabel": "无权读取"}}
    if all(can_read_source(actor, code) for code in (PURCHASE_RECEIPT_READ_PERMISSION,
                                              INVENTORY_READ_PERMISSION, INVENTORY_TRANSACTION_READ_PERMISSION)):
        receipts = list(PurchaseReceipt.objects.filter(source_purchase_order=order, status__in=["received", "closed"]))
        inbounds = list(WarehouseInbound.objects.filter(source_inspection__source_receipt__in=receipts,
            warehouse__company_id=order.company_id, status__in=["completed", "closed"]))
        checks["quantity"] = compare_quantities(order, receipts, inbounds)
    if can_read_source(actor, PURCHASE_INSPECTION_READ_PERMISSION):
        from procurement.models import PurchaseInspection
        records = list(PurchaseInspection.objects.filter(source_receipt__source_purchase_order=order)
            .select_related("source_receipt__source_purchase_order"))
        complete = bool(records) and all((quality_projection(row)["lineReleaseFacts"] or {}).get("qualityReleaseStatus")
            in {"RELEASED", "REJECTED"} for row in records)
        checks["quality"] = {"statusLabel": "已有逐行放行依据" if complete else "待核",
            "inspectionNos": [row.inspection_no for row in records],
            "reason": "" if complete else "缺少正式逐行质检放行依据。"}
    if can_read_source(actor, PAYABLE_CHECK_READ_PERMISSION):
        matched = PurchaseReconciliation.objects.filter(company_id=actor.company_id,
            purchase_order_no=order.po_no, status=PurchaseReconciliation.Status.MATCHED)
        facts = []
        for row in matched:
            payable = PayableCheckAuthorityRecord.objects.filter(company_id=actor.company_id,
                legal_entity_id=row.legal_entity_id, tenant_id=row.tenant_id, currency=row.currency,
                ledger_book_id=row.ledger_book_id, supplier_id=row.supplier_id,
                payable_check_no=row.source_payable_check_no).first()
            if payable and payable.checked_amount == row.settlement_amount and row.checked_at:
                facts.append({"payableNo": payable.payable_check_no, "reconciliationNo": row.reconciliation_no,
                    "amount": str(payable.checked_amount), "currency": payable.currency})
        checks["payable"] = {"statusLabel": "已核对" if facts else "待核", "documents": facts,
            "reason": "" if facts else "缺少与本采购单关联的正式应付金额核对依据。"}
    return checks


def eligible_differences(actor, order_no):
    return PurchaseReconciliationDifference.objects.filter(
        reconciliation__company_id=actor.company_id, reconciliation__purchase_order_no=order_no,
        blocking=True, difference_code__in=CATEGORIES,
    ).select_related("reconciliation")


def category(difference):
    return CATEGORIES[difference.difference_code]


def formal_difference(difference):
    rec = difference.reconciliation
    return (difference.expected_value != difference.actual_value
        and rec.status == "difference_found" and rec.checked_at is not None
        and rec.check_executions.filter(expected_version=difference.check_version - 1,
            result_status="difference_found").exists())


def case_authority(actor, difference):
    responsibility = RISK_HANDLERS[category(difference)][0]
    return {
        "receive": allowed(actor, RISK_RECEIVE),
        "close": allowed(actor, RISK_CLOSE),
        "handler": allowed(actor, responsibility),
    }


def public_difference(difference):
    return {"id": difference.pk, "sourceNo": difference.reconciliation.reconciliation_no,
        "field": difference.field_name, "expected": difference.expected_value,
        "actual": difference.actual_value, "department": RISK_HANDLERS[category(difference)][1]}


def row_facts(actor, risk, permissions):
    risk_type = type(risk).__name__
    entries = list(history(actor, risk_type, risk.pk))
    transitions = BusinessStateTransition.objects.filter(object_type=risk_type, object_id=risk.pk).order_by("version")
    transition_ids = list(transitions.values_list("audit_reference", flat=True))
    consistent = len(transition_ids) == risk.version - 1 and transition_ids == [
        f"organization-operating-audit:{entry.pk}" for entry in entries[1:]]
    actions = []
    action = None
    if consistent and risk.status == "received" and permissions["handler"] and actor.pk == risk.handler_id:
        action = "process"
    if consistent and risk.status == "processed" and permissions["close"] and actor.pk != risk.handler_id:
        if all(entry.actor_id != actor.pk for entry in entries):
            action = "close"
    if action:
        actions.append({"type": action, "code": ACTIONS[action][0], "label": ACTIONS[action][1]})
    return {"statusLabel": risk.get_status_display(), "id": risk.pk, "version": risk.version,
        "handler": risk.handler.real_name, "history": [audit_row(entry) for entry in entries],
        "statusTransitionHistory": list(transitions.values("source_state", "target_state",
            "operator_id", "reason", "timestamp", "audit_reference")),
        "statusTransitionCount": len(transition_ids), "stateMachineConsistent": consistent,
        "actions": actions}


def apply_risk_action(actor, risk, rights, action, data, source_no, source):
    facts = row_facts(actor, risk, rights)
    if action not in {item["type"] for item in facts["actions"]}:
        raise PermissionDenied("当前动作不可用。关闭必须由未参与受理或处理的授权复核人办理。")
    if data["expectedVersion"] != risk.version:
        return None
    if action == "process":
        risk.disposition = data["evidence"]
        risk.save(update_fields=["disposition"])
    target = "processed" if action == "process" else "closed"
    action_code = ACTIONS[action][0]
    entry = audit(actor, action_code, risk, source_no, data["reason"], {"status": risk.get_status_display()},
        {"status": dict(risk.Status.choices)[target], "source": source, "evidence": data["evidence"]})
    transition_business_object(business_object=risk, object_type=type(risk).__name__, source_state=risk.status,
        target_state=target, action_code=action_code, operator=actor, reason=data["reason"],
        audit_reference=f"organization-operating-audit:{entry.pk}", allowed_transitions=TRANSITIONS)
    return row_facts(actor, risk, rights)


class ProcurementRiskDirectoryView(EnterpriseView):
    def get(self, request, order_no):
        actor = request.user
        can_check = allowed(actor, RISK_CHECK)
        if not any(allowed(actor, code) for code in (RISK_CHECK, RISK_RECEIVE, RISK_CLOSE,
                                            *(x[0] for x in RISK_HANDLERS.values()))):
            raise PermissionDenied("当前岗位没有采购核对或风险权限。")
        try:
            order = PurchaseOrder.objects.filter(po_no=order_no, company_id=actor.company_id).first()
            if not order:
                raise NotFound("没有可核对的采购单。")
            results = []
            for difference in eligible_differences(actor, order_no):
                if not formal_difference(difference):
                    continue
                rights = case_authority(actor, difference)
                risk = ProcurementEvidenceRisk.objects.filter(difference=difference).select_related("handler").first()
                if not (rights["receive"] or rights["close"] or (rights["handler"] and risk and risk.handler_id == actor.pk)):
                    continue
                item = public_difference(difference)
                if risk:
                    item["risk"] = row_facts(actor, risk, rights)
                elif rights["receive"]:
                    code = RISK_HANDLERS[category(difference)][0]
                    item["action"] = {"type": "receive", "code": ACTIONS["receive"][0], "label": ACTIONS["receive"][1]}
                    users = User.objects.filter(company_id=actor.company_id, is_active=True)
                    item["handlers"] = [{"id": user.pk, "name": user.real_name} for user in users if allowed(user, code)]
                results.append(item)
            return response(request, {"orderNo": order.po_no,
                "checks": source_checks(actor, order) if can_check else None, "differences": results})
        except DatabaseError:
            return read_failure(request)

    @transaction.atomic
    def post(self, request, order_no):
        actor = request.user
        if not allowed(actor, RISK_RECEIVE):
            raise PermissionDenied("当前岗位没有受理权限。")
        data = validated(ReceiveInput, request)
        difference = eligible_differences(actor, order_no).select_for_update().filter(pk=data["differenceId"]).first()
        if not difference or not formal_difference(difference):
            raise ValidationError("原单尚无对应的正式差异依据，当前只能待核。")
        handler = User.objects.filter(company_id=actor.company_id, is_active=True, pk=data["handlerId"]).first()
        if not handler or not allowed(handler, RISK_HANDLERS[category(difference)][0]):
            raise ValidationError("所选账号没有该类风险处理权限。")
        if ProcurementEvidenceRisk.objects.filter(difference=difference).exists():
            return conflict("该正式差异已有风险记录。")
        risk = create_business_object_with_initial_state(model=ProcurementEvidenceRisk,
            initial_state="received", difference=difference, handler=handler)
        audit(actor, ACTIONS["receive"][0], risk, order_no, data["reason"], {},
              {"handler": handler.real_name, "handlerId": handler.pk, "source": public_difference(difference)})
        return response(request, {"risk": row_facts(actor, risk, case_authority(actor, difference))})


class ProcurementRiskActionView(EnterpriseView):
    @transaction.atomic
    def post(self, request, order_no, risk_id, action):
        actor = request.user
        data = validated(UpdateInput, request)
        risk = ProcurementEvidenceRisk.objects.select_for_update().select_related("difference__reconciliation", "handler").filter(
            pk=risk_id, difference__in=eligible_differences(actor, order_no)).first()
        if not risk or not formal_difference(risk.difference):
            raise NotFound("当前范围没有对应且仍有效的正式风险记录。")
        rights = case_authority(actor, risk.difference)
        if not any(rights.values()) or (not rights["close"] and not rights["receive"] and actor.pk != risk.handler_id):
            raise NotFound("当前范围没有对应风险记录。")
        facts = apply_risk_action(actor, risk, rights, action, data, order_no, public_difference(risk.difference))
        if facts is None:
            return conflict("风险记录已变化，请读取最新记录。")
        return response(request, {"risk": facts})
