"""Formal PO -> supplier settlement actions for PCE 14-22.

This module deliberately never imports or calls the V8.x demo/canary seed helpers.
Every public write is one explicit, authorized, transactional business action.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import re
import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from procurement.business_action_control import authorize_action
from procurement.models import (
    InventoryTransaction,
    PurchaseInspection,
    PurchaseOrder,
    PurchaseReceipt,
    WarehouseInbound,
)
from system.models import PositionWorkflowResponsibility
from workflow_runtime.models import WorkflowNodeDefinition
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import (
    BuyerPerformanceMetric,
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierPaymentStatusRecord,
    SupplierPerformanceMetric,
    SupplierReconciliation,
    SupplierReconciliationConfirmation,
    SupplierReconciliationDifference,
    SupplierSettlementActionAudit,
    SupplierSettlementCompletion,
)
from .services import (
    transition_confirmation,
    transition_difference,
    transition_payable_confirmation,
    transition_payment_request,
    transition_payment_status_record,
    transition_reconciliation,
    transition_settlement_completion,
)


FORMAL_VERSION = "PCE-SUPPLIER-SETTLEMENT-14-22-V1.0"
PROCESS_CODE = "PROCUREMENT_SUPPLIER_SETTLEMENT_V1"
BATCH_ID = "PCE-SUPPLIER-SETTLEMENT-14-22-V1.0"

ACTION_CREATE_RECONCILIATION = "scm.supplier_reconciliation.create"
ACTION_ANALYZE_DIFFERENCES = "scm.supplier_reconciliation.analyze"
ACTION_CONFIRM_RECONCILIATION = "scm.supplier_reconciliation.confirm"
ACTION_CONFIRM_PAYABLE = "scm.supplier_payable.confirm"
ACTION_CREATE_PAYMENT_REQUEST = "scm.supplier_payment_request.create"
ACTION_SUBMIT_PAYMENT_REQUEST = "scm.supplier_payment_request.submit"
ACTION_APPROVE_PAYMENT_REQUEST = "scm.supplier_payment_request.approve"
ACTION_RELEASE_PAYMENT_REQUEST = "scm.supplier_payment_request.release"
ACTION_RECORD_PAYMENT_STATUS = "scm.supplier_payment_status.record"
ACTION_COMPLETE_SETTLEMENT = "scm.supplier_settlement.complete"
ACTION_CALCULATE_SUPPLIER_PERFORMANCE = "scm.supplier_performance.calculate"
ACTION_CALCULATE_BUYER_PERFORMANCE = "scm.buyer_performance.calculate"

ACTION_LABELS = {
    ACTION_CREATE_RECONCILIATION: "创建供应商对账",
    ACTION_ANALYZE_DIFFERENCES: "执行基础差异分析",
    ACTION_CONFIRM_RECONCILIATION: "确认供应商对账",
    ACTION_CONFIRM_PAYABLE: "确认供应商应付",
    ACTION_CREATE_PAYMENT_REQUEST: "创建付款申请",
    ACTION_SUBMIT_PAYMENT_REQUEST: "提交付款申请",
    ACTION_APPROVE_PAYMENT_REQUEST: "批准付款申请",
    ACTION_RELEASE_PAYMENT_REQUEST: "转入待付款处理",
    ACTION_RECORD_PAYMENT_STATUS: "记录付款业务状态",
    ACTION_COMPLETE_SETTLEMENT: "确认供应商结算完成",
    ACTION_CALCULATE_SUPPLIER_PERFORMANCE: "计算供应商绩效",
    ACTION_CALCULATE_BUYER_PERFORMANCE: "计算采购员绩效",
}


class FormalActionBlocked(ValueError):
    def __init__(self, code, message, http_status=409):
        super().__init__(code)
        self.code = code
        self.message = message
        self.http_status = http_status


def _money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _number(prefix, source_id):
    return f"{prefix}-{date.today():%Y%m%d}-{int(source_id):06d}"


def _safe_code(value):
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "UNKNOWN").upper()).strip("-")[:32]


def _order_for_reconciliation(reconciliation):
    refs = list(reconciliation.purchase_order_ids or [])
    if len(refs) != 1:
        raise FormalActionBlocked(
            "RECONCILIATION_SOURCE_ORDER_CARDINALITY_INVALID",
            "正式对账必须且只能关联一个明确采购订单。",
        )
    order = PurchaseOrder.objects.select_related(
        "supplier", "buyer_employee", "purchase_department", "department"
    ).prefetch_related("items__material").filter(po_no=refs[0]).first()
    if not order:
        raise FormalActionBlocked("SOURCE_PURCHASE_ORDER_NOT_FOUND", "来源采购订单不存在。")
    return order


def _chain_from_source(source):
    try:
        if isinstance(source, PurchaseOrder):
            return source, None, None, None, None
        if isinstance(source, SupplierReconciliation):
            return _order_for_reconciliation(source), source, None, None, None
        if isinstance(source, SupplierPayableConfirmation):
            reconciliation = SupplierReconciliation.objects.get(
                reconciliation_no=source.reconciliation_no
            )
            return _order_for_reconciliation(reconciliation), reconciliation, source, None, None
        if isinstance(source, SupplierPaymentRequest):
            payable = SupplierPayableConfirmation.objects.get(
                payable_confirmation_no=source.payable_confirmation_no
            )
            reconciliation = SupplierReconciliation.objects.get(
                reconciliation_no=payable.reconciliation_no
            )
            return _order_for_reconciliation(reconciliation), reconciliation, payable, source, None
        if isinstance(source, SupplierPaymentStatusRecord):
            request = SupplierPaymentRequest.objects.get(payment_request_no=source.payment_request_no)
            order, reconciliation, payable, request, _ = _chain_from_source(request)
            return order, reconciliation, payable, request, source
        if isinstance(source, SupplierSettlementCompletion):
            request = SupplierPaymentRequest.objects.get(payment_request_no=source.payment_request_no)
            order, reconciliation, payable, request, payment = _chain_from_source(request)
            payment = SupplierPaymentStatusRecord.objects.get(
                payment_request_no=request.payment_request_no
            )
            return order, reconciliation, payable, request, payment
    except ObjectDoesNotExist as exc:
        raise FormalActionBlocked(
            "FORMAL_SOURCE_CHAIN_INCOMPLETE",
            "来源业务链不完整，禁止继续执行正式动作。",
        ) from exc
    raise FormalActionBlocked("FORMAL_SOURCE_TYPE_INVALID", "正式业务动作来源类型不受支持。")


def _source_for_action(action_code, source_id):
    model_map = {
        ACTION_CREATE_RECONCILIATION: PurchaseOrder,
        ACTION_ANALYZE_DIFFERENCES: SupplierReconciliation,
        ACTION_CONFIRM_RECONCILIATION: SupplierReconciliation,
        ACTION_CONFIRM_PAYABLE: SupplierReconciliation,
        ACTION_CREATE_PAYMENT_REQUEST: SupplierPayableConfirmation,
        ACTION_SUBMIT_PAYMENT_REQUEST: SupplierPaymentRequest,
        ACTION_APPROVE_PAYMENT_REQUEST: SupplierPaymentRequest,
        ACTION_RELEASE_PAYMENT_REQUEST: SupplierPaymentRequest,
        ACTION_RECORD_PAYMENT_STATUS: SupplierPaymentRequest,
        ACTION_COMPLETE_SETTLEMENT: SupplierPaymentStatusRecord,
        ACTION_CALCULATE_SUPPLIER_PERFORMANCE: SupplierSettlementCompletion,
        ACTION_CALCULATE_BUYER_PERFORMANCE: SupplierSettlementCompletion,
    }
    model = model_map.get(action_code)
    if not model:
        raise FormalActionBlocked("FORMAL_ACTION_NOT_REGISTERED", "业务动作未登记。")
    source = model.objects.filter(pk=source_id).first()
    if not source:
        raise FormalActionBlocked("FORMAL_SOURCE_NOT_FOUND", "业务动作来源对象不存在。", 404)
    return source


def inspect_formal_action(*, user, action_code, source_id):
    source = _source_for_action(action_code, source_id)
    order, reconciliation, payable, request, payment = _chain_from_source(source)
    organization_id = str(order.company_id)
    decision = authorize_action(
        user=user,
        action_code=action_code,
        organization_id=organization_id,
        business_object={
            "organizationId": organization_id,
            "departmentId": order.purchase_department_id or order.department_id,
            "ownerUserId": order.created_by,
        },
    )
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        process_definition__definition_code=PROCESS_CODE,
        process_definition__active=True,
        business_action_code=action_code,
        active=True,
    ).first()
    mapping = (
        PositionWorkflowResponsibility.objects.select_related("responsibility").filter(
            position=position,
            workflow_node=node,
            active=True,
            responsibility__is_active=True,
            responsibility__status="ACTIVE",
        ).first()
        if position and node
        else None
    )
    allowed = bool(
        decision.get("allowed")
        and employee
        and employee.status == "active"
        and position
        and position.is_active
        and mapping
    )
    if not allowed:
        message = (
            decision.get("reason")
            if not decision.get("allowed")
            else "当前账号缺少有效的员工—岗位—职责—流程节点执行链。"
        )
        raise FormalActionBlocked("FORMAL_ACTION_AUTHORIZATION_DENIED", message, 403)
    identity = {
        "account": {"id": user.pk, "username": user.username, "realName": user.real_name},
        "employee": {"id": employee.pk, "employeeNo": employee.employee_no, "name": employee.full_name},
        "position": {"id": position.pk, "code": position.code, "name": position.name},
        "responsibility": {
            "id": mapping.responsibility_id,
            "code": mapping.responsibility.code,
            "name": mapping.responsibility.name,
        },
        "workflowNode": {"id": node.pk, "code": node.node_code, "name": node.node_name},
        "authorization": {
            "allowed": True,
            "decisionCode": decision.get("decisionCode"),
            "permissionCodes": decision.get("permissionCodes", []),
            "roleCodes": decision.get("roleCodes", []),
            "scope": decision.get("scope", {}),
            "authoritySource": decision.get("authoritySource", ""),
        },
    }
    return {
        "source": source,
        "order": order,
        "reconciliation": reconciliation,
        "payable": payable,
        "request": request,
        "payment": payment,
        "decision": decision,
        "identity": identity,
    }


def _audit(*, user, action_code, context, source_type, source_no, target, target_no,
           before_status, after_status, amount, reason, extra=None):
    roles = context["decision"].get("roleCodes", [])
    return SupplierSettlementActionAudit.objects.create(
        action_no=f"SSA-FORMAL-{uuid.uuid4().hex.upper()}",
        action_code=action_code,
        operator=user,
        role=",".join(roles)[:80],
        object_type=target.__class__.__name__,
        object_id=target.pk,
        object_no=str(target_no)[:80],
        before_status=str(before_status or "")[:40],
        after_status=str(after_status or "")[:40],
        reason=str(reason or ACTION_LABELS[action_code])[:240],
        source_object_type=source_type,
        source_object_no=str(source_no)[:80],
        amount=_money(amount),
        authorization_result=context["decision"].get("decisionCode", ""),
        evidence={
            **context["identity"],
            "action": {"code": action_code, "label": ACTION_LABELS[action_code]},
            "source": {"type": source_type, "no": source_no},
            "target": {"type": target.__class__.__name__, "id": target.pk, "no": target_no},
            "amount": str(_money(amount)),
            "beforeStatus": before_status,
            "afterStatus": after_status,
            "formalVersion": FORMAL_VERSION,
            "safety": {
                "paymentExecutionWriteCount": 0,
                "bankSendWriteCount": 0,
                "fundDeductionCount": 0,
                "generalLedgerWriteCount": 0,
            },
            **(extra or {}),
        },
        tenant_id=str(context["order"].company_id),
        legal_entity_id=str(context["order"].company_id),
    )


def _fulfillment_facts(order):
    order = PurchaseOrder.objects.select_for_update().select_related(
        "supplier", "buyer_employee"
    ).prefetch_related("items__material").get(pk=order.pk)
    if order.status != "closed":
        raise FormalActionBlocked("PURCHASE_ORDER_NOT_SETTLEMENT_ELIGIBLE", "采购订单尚未完成履约结案。")
    if not order.supplier or not order.supplier.is_active:
        raise FormalActionBlocked("SUPPLIER_INACTIVE", "采购订单供应商不存在或已停用。")
    items = list(order.items.all())
    if not items:
        raise FormalActionBlocked("PURCHASE_ORDER_ITEMS_REQUIRED", "采购订单没有正式明细。")
    receipts = list(PurchaseReceipt.objects.filter(source_purchase_order=order).order_by("pk"))
    inspections = list(PurchaseInspection.objects.filter(
        source_receipt__source_purchase_order=order
    ).order_by("pk"))
    inbounds = list(WarehouseInbound.objects.filter(
        source_inspection__source_receipt__source_purchase_order=order,
        status="completed",
    ).order_by("pk"))
    transactions = list(InventoryTransaction.objects.filter(
        source_inbound__source_inspection__source_receipt__source_purchase_order=order,
        direction="IN",
    ).order_by("pk"))
    if not receipts or not inspections or not inbounds or not transactions:
        raise FormalActionBlocked("FULFILLMENT_SOURCE_CHAIN_INCOMPLETE", "收货、检验、入库或库存交易来源链不完整。")
    receipt_ids = {row.pk for row in receipts}
    if any(row.source_receipt_id not in receipt_ids for row in inspections):
        raise FormalActionBlocked("FULFILLMENT_SOURCE_CHAIN_MISMATCH", "检验来源与采购订单不一致。")
    inspection_ids = {row.pk for row in inspections}
    if any(row.source_inspection_id not in inspection_ids for row in inbounds):
        raise FormalActionBlocked("FULFILLMENT_SOURCE_CHAIN_MISMATCH", "入库来源与检验单不一致。")
    inbound_ids = {row.pk for row in inbounds}
    if any(row.source_inbound_id not in inbound_ids for row in transactions):
        raise FormalActionBlocked("FULFILLMENT_SOURCE_CHAIN_MISMATCH", "库存交易来源与入库单不一致。")
    ordered_qty = sum((Decimal(row.quantity) for row in items), Decimal("0"))
    receipt_qty = sum((Decimal(row.quantity) for row in receipts), Decimal("0"))
    qualified_qty = sum((Decimal(row.qualified_quantity) for row in inspections), Decimal("0"))
    inbound_qty = sum((Decimal(row.quantity) for row in inbounds), Decimal("0"))
    transaction_qty = sum((Decimal(row.quantity) for row in transactions), Decimal("0"))
    if inbound_qty <= 0 or transaction_qty != inbound_qty:
        raise FormalActionBlocked("INBOUND_QUANTITY_INVALID", "正式入库数量必须大于0且与库存交易数量一致。")
    purchase_amount = _money(sum((Decimal(row.quantity) * Decimal(row.unit_price) for row in items), Decimal("0")))
    settlement_unit_price = (
        purchase_amount / ordered_qty if ordered_qty else Decimal("0")
    )
    reconciliation_amount = _money(inbound_qty * settlement_unit_price)
    received_amount = _money(receipt_qty * settlement_unit_price)
    qualified_amount = _money(qualified_qty * settlement_unit_price)
    currency_values = {str(row.currency_snapshot or "CNY") for row in items}
    if len(currency_values) != 1:
        raise FormalActionBlocked("PURCHASE_ORDER_CURRENCY_MISMATCH", "采购订单明细币种不一致。")
    return {
        "order": order,
        "items": items,
        "receipts": receipts,
        "inspections": inspections,
        "inbounds": inbounds,
        "transactions": transactions,
        "orderedQty": ordered_qty,
        "receiptQty": receipt_qty,
        "qualifiedQty": qualified_qty,
        "inboundQty": inbound_qty,
        "purchaseAmount": purchase_amount,
        "receivedAmount": received_amount,
        "qualifiedAmount": qualified_amount,
        "reconciliationAmount": reconciliation_amount,
        "orderUnitPrice": _money(settlement_unit_price),
        "settlementUnitPrice": _money(settlement_unit_price),
        "currency": next(iter(currency_values)),
    }


def _result(action_code, target, target_no, audit, *, replay=False, extra=None):
    return {
        "formalVersion": FORMAL_VERSION,
        "actionCode": action_code,
        "actionLabel": ACTION_LABELS[action_code],
        "targetType": target.__class__.__name__,
        "targetId": target.pk,
        "targetNo": target_no,
        "statusCode": getattr(target, "status", "calculated"),
        "statusLabel": target.get_status_display() if hasattr(target, "get_status_display") else "已计算",
        "auditNo": audit.action_no,
        "idempotentReplay": replay,
        "authorizedBusinessWriteCount": 0 if replay else 1,
        "unauthorizedBusinessWriteCount": 0,
        "safety": {
            "paymentExecutionWriteCount": 0,
            "bankSendWriteCount": 0,
            "fundDeductionCount": 0,
            "generalLedgerWriteCount": 0,
        },
        **(extra or {}),
    }


@transaction.atomic
def execute_formal_action(*, user, action_code, source_id, reason):
    context = inspect_formal_action(user=user, action_code=action_code, source_id=source_id)
    handlers = {
        ACTION_CREATE_RECONCILIATION: _create_reconciliation,
        ACTION_ANALYZE_DIFFERENCES: _analyze_differences,
        ACTION_CONFIRM_RECONCILIATION: _confirm_reconciliation,
        ACTION_CONFIRM_PAYABLE: _confirm_payable,
        ACTION_CREATE_PAYMENT_REQUEST: _create_payment_request,
        ACTION_SUBMIT_PAYMENT_REQUEST: _transition_request,
        ACTION_APPROVE_PAYMENT_REQUEST: _transition_request,
        ACTION_RELEASE_PAYMENT_REQUEST: _transition_request,
        ACTION_RECORD_PAYMENT_STATUS: _record_payment_status,
        ACTION_COMPLETE_SETTLEMENT: _complete_settlement,
        ACTION_CALCULATE_SUPPLIER_PERFORMANCE: _calculate_supplier_performance,
        ACTION_CALCULATE_BUYER_PERFORMANCE: _calculate_buyer_performance,
    }
    return handlers[action_code](user, context, str(reason or ACTION_LABELS[action_code]).strip(), action_code)


def _create_reconciliation(user, context, reason, action_code):
    facts = _fulfillment_facts(context["order"])
    existing = next((row for row in SupplierReconciliation.objects.select_for_update().all()
                     if facts["order"].po_no in (row.purchase_order_ids or [])), None)
    if existing:
        audit = _audit(user=user, action_code=action_code, context=context,
                       source_type="PurchaseOrder", source_no=facts["order"].po_no,
                       target=existing, target_no=existing.reconciliation_no,
                       before_status=existing.status, after_status=existing.status,
                       amount=existing.reconciliation_amount, reason=f"{reason} / 幂等重放")
        return _result(action_code, existing, existing.reconciliation_no, audit, replay=True,
                       extra={"amount": str(existing.reconciliation_amount)})
    reconciliation = create_business_object_with_initial_state(
        model=SupplierReconciliation,
        initial_state="draft",
        reconciliation_no=_number("SR", facts["order"].pk),
        supplier_id=facts["order"].supplier.code,
        supplier_name=facts["order"].supplier.name,
        period=f"{facts['order'].order_date:%Y-%m}",
        purchase_order_ids=[facts["order"].po_no],
        receipt_ids=[row.receipt_no for row in facts["receipts"]],
        inspection_ids=[row.inspection_no for row in facts["inspections"]],
        warehouse_receipt_ids=[row.inbound_no for row in facts["inbounds"]],
        inventory_transaction_ids=[row.transaction_no for row in facts["transactions"]],
        purchase_amount=facts["purchaseAmount"],
        received_amount=facts["receivedAmount"],
        qualified_amount=facts["qualifiedAmount"],
        reconciliation_amount=facts["reconciliationAmount"],
        tenant_id=str(facts["order"].company_id),
        batch_id=BATCH_ID,
    )
    audit = _audit(
        user=user, action_code=action_code, context=context,
        source_type="PurchaseOrder", source_no=facts["order"].po_no,
        target=reconciliation, target_no=reconciliation.reconciliation_no,
        before_status="", after_status="draft", amount=reconciliation.reconciliation_amount,
        reason=reason,
        extra={"sourceRelations": {
            "purchaseOrders": [{"id": facts["order"].pk, "no": facts["order"].po_no}],
            "receipts": [{"id": row.pk, "no": row.receipt_no} for row in facts["receipts"]],
            "inspections": [{"id": row.pk, "no": row.inspection_no} for row in facts["inspections"]],
            "inbounds": [{"id": row.pk, "no": row.inbound_no} for row in facts["inbounds"]],
            "inventoryTransactions": [{"id": row.pk, "no": row.transaction_no} for row in facts["transactions"]],
        }, "calculation": {
            "settlementQuantity": str(facts["inboundQty"]),
            "settlementUnitPrice": str(facts["settlementUnitPrice"]),
            "reconciliationAmount": str(facts["reconciliationAmount"]),
            "currency": facts["currency"],
        }},
    )
    return _result(action_code, reconciliation, reconciliation.reconciliation_no, audit,
                   extra={"amount": str(reconciliation.reconciliation_amount), "currency": facts["currency"]})


def _analyze_differences(user, context, reason, action_code):
    reconciliation = SupplierReconciliation.objects.select_for_update().get(pk=context["source"].pk)
    if reconciliation.status != "draft":
        raise FormalActionBlocked("RECONCILIATION_NOT_DRAFT", "只有草稿对账可以执行基础差异分析。")
    order = _order_for_reconciliation(reconciliation)
    facts = _fulfillment_facts(order)
    values = {
        "quantity_difference": facts["orderedQty"] - facts["inboundQty"],
        "price_difference": facts["orderUnitPrice"] - facts["settlementUnitPrice"],
        "amount_difference": facts["purchaseAmount"] - facts["reconciliationAmount"],
    }
    existing = list(SupplierReconciliationDifference.objects.select_for_update().filter(
        reconciliation_no=reconciliation.reconciliation_no
    ))
    replay = bool(existing)
    if existing and {row.difference_type for row in existing} != set(values):
        raise FormalActionBlocked("DIFFERENCE_FACT_SET_CONFLICT", "已有差异事实集合不完整或冲突。")
    rows = existing
    if not rows:
        source_refs = {
            "purchaseOrders": reconciliation.purchase_order_ids,
            "receipts": reconciliation.receipt_ids,
            "inspections": reconciliation.inspection_ids,
            "inbounds": reconciliation.warehouse_receipt_ids,
            "inventoryTransactions": reconciliation.inventory_transaction_ids,
            "currency": facts["currency"],
        }
        buyer = order.buyer_employee
        suffixes = {"quantity_difference": "QTY", "price_difference": "PRICE", "amount_difference": "AMOUNT"}
        for difference_type, value in values.items():
            row = create_business_object_with_initial_state(
                model=SupplierReconciliationDifference,
                initial_state="draft",
                difference_no=f"SRD-{reconciliation.pk:06d}-{suffixes[difference_type]}",
                reconciliation_no=reconciliation.reconciliation_no,
                supplier_id=reconciliation.supplier_id,
                supplier_name=reconciliation.supplier_name,
                buyer_id=buyer.employee_no if buyer else str(order.buyer or ""),
                buyer_name=buyer.full_name if buyer else str(order.buyer or ""),
                difference_type=difference_type,
                difference_amount=_money(value if difference_type != "quantity_difference" else 0),
                difference_quantity=(Decimal(value) if difference_type == "quantity_difference" else Decimal("0")),
                responsibility_type="unknown",
                occurred_at=date.today(),
                source_object_refs={**source_refs, "calculatedValue": str(value)},
                tenant_id=reconciliation.tenant_id,
                batch_id=BATCH_ID,
            )
            target_states = ["analyzing"] if value != 0 else [
                "analyzing", "responsibility_confirmed", "supplier_communicating", "closed"
            ]
            for state in target_states:
                transition_difference(row, state, user, f"{reason} / {row.get_difference_type_display()}")
            rows.append(row)
    audit = _audit(
        user=user, action_code=action_code, context=context,
        source_type="SupplierReconciliation", source_no=reconciliation.reconciliation_no,
        target=reconciliation, target_no=reconciliation.reconciliation_no,
        before_status=reconciliation.status, after_status=reconciliation.status,
        amount=reconciliation.reconciliation_amount,
        reason=f"{reason}{' / 幂等重放' if replay else ''}",
        extra={"differenceFacts": {key: str(value) for key, value in values.items()},
               "differenceNos": [row.difference_no for row in rows]},
    )
    return _result(action_code, reconciliation, reconciliation.reconciliation_no, audit, replay=replay,
                   extra={"quantityDifference": str(values["quantity_difference"]),
                          "priceDifference": str(values["price_difference"]),
                          "amountDifference": str(values["amount_difference"]),
                          "differenceNos": [row.difference_no for row in rows]})


def _confirm_reconciliation(user, context, reason, action_code):
    reconciliation = SupplierReconciliation.objects.select_for_update().get(pk=context["source"].pk)
    differences = list(SupplierReconciliationDifference.objects.select_for_update().filter(
        reconciliation_no=reconciliation.reconciliation_no
    ).order_by("pk"))
    if len(differences) != 3 or any(row.status != "closed" for row in differences):
        raise FormalActionBlocked("DIFFERENCE_ANALYSIS_NOT_CLOSED", "数量、价格、金额三项基础差异尚未全部关闭。")
    replay = reconciliation.status == "completed"
    if not replay and reconciliation.status != "draft":
        raise FormalActionBlocked("RECONCILIATION_CONFIRM_STATE_INVALID", "当前对账状态不能确认。")
    confirmation_nos = []
    for difference in differences:
        confirmation = SupplierReconciliationConfirmation.objects.filter(
            difference_no=difference.difference_no
        ).first()
        if not confirmation:
            confirmation = create_business_object_with_initial_state(
                model=SupplierReconciliationConfirmation,
                initial_state="waiting_supplier",
                confirmation_no=f"SRC-{difference.pk:06d}",
                difference_no=difference.difference_no,
                supplier_id=difference.supplier_id,
                supplier_response="accepted",
                supplier_comment="基础数量、价格、金额差异均为零；由授权人员显式确认。",
                confirmed_by=user.get_username(),
                confirmed_at=timezone.now(),
                tenant_id=difference.tenant_id,
                batch_id=BATCH_ID,
            )
            for state in ("supplier_confirmed", "internal_verified", "completed"):
                transition_confirmation(confirmation, state, user, reason)
        confirmation_nos.append(confirmation.confirmation_no)
    if not replay:
        for state in ("internal_review", "supplier_confirming", "completed"):
            transition_reconciliation(reconciliation, state, user, reason)
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierReconciliation", source_no=reconciliation.reconciliation_no,
                   target=reconciliation, target_no=reconciliation.reconciliation_no,
                   before_status="completed" if replay else "draft", after_status="completed",
                   amount=reconciliation.reconciliation_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}",
                   extra={"confirmationNos": confirmation_nos})
    return _result(action_code, reconciliation, reconciliation.reconciliation_no, audit, replay=replay,
                   extra={"confirmationNos": confirmation_nos, "amount": str(reconciliation.reconciliation_amount)})


def _confirm_payable(user, context, reason, action_code):
    reconciliation = SupplierReconciliation.objects.select_for_update().get(pk=context["source"].pk)
    if reconciliation.status != "completed":
        raise FormalActionBlocked("RECONCILIATION_NOT_CONFIRMED", "供应商对账尚未完成确认。")
    payable = SupplierPayableConfirmation.objects.select_for_update().filter(
        reconciliation_no=reconciliation.reconciliation_no
    ).first()
    replay = bool(payable)
    if not payable:
        payable = create_business_object_with_initial_state(
            model=SupplierPayableConfirmation,
            initial_state="draft",
            payable_confirmation_no=_number("SPC", reconciliation.pk),
            supplier_id=reconciliation.supplier_id,
            supplier_name=reconciliation.supplier_name,
            reconciliation_no=reconciliation.reconciliation_no,
            period=reconciliation.period,
            confirmed_amount=reconciliation.reconciliation_amount,
            qualified_amount=reconciliation.qualified_amount,
            deduction_amount=Decimal("0"),
            final_payable_amount=reconciliation.reconciliation_amount,
            source_object_refs={
                "reconciliationNo": reconciliation.reconciliation_no,
                "purchaseOrderNos": reconciliation.purchase_order_ids,
                "currency": "CNY",
            },
            tenant_id=reconciliation.tenant_id,
            legal_entity_id=reconciliation.tenant_id,
            batch_id=BATCH_ID,
        )
        for state in ("internal_review", "confirmed", "ready_for_payment_request"):
            transition_payable_confirmation(payable, state, user, reason)
    elif payable.final_payable_amount != reconciliation.reconciliation_amount:
        raise FormalActionBlocked("PAYABLE_AMOUNT_CONFLICT", "已有应付金额与已确认对账金额不一致。")
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierReconciliation", source_no=reconciliation.reconciliation_no,
                   target=payable, target_no=payable.payable_confirmation_no,
                   before_status=payable.status if replay else "", after_status=payable.status,
                   amount=payable.final_payable_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}")
    return _result(action_code, payable, payable.payable_confirmation_no, audit, replay=replay,
                   extra={"amount": str(payable.final_payable_amount)})


def _create_payment_request(user, context, reason, action_code):
    payable = SupplierPayableConfirmation.objects.select_for_update().get(pk=context["source"].pk)
    if payable.status != "ready_for_payment_request":
        raise FormalActionBlocked("PAYABLE_NOT_READY", "应付确认尚未达到可申请付款状态。")
    request = SupplierPaymentRequest.objects.select_for_update().filter(
        payable_confirmation_no=payable.payable_confirmation_no
    ).first()
    replay = bool(request)
    if not request:
        request = create_business_object_with_initial_state(
            model=SupplierPaymentRequest,
            initial_state="draft",
            payment_request_no=_number("SPR", payable.pk),
            payable_confirmation_no=payable.payable_confirmation_no,
            supplier_id=payable.supplier_id,
            supplier_name=payable.supplier_name,
            period=payable.period,
            request_amount=payable.final_payable_amount,
            request_reason="系统流程验收：已确认对账形成正式付款申请；不执行付款。",
            requested_by=user.get_username(),
            tenant_id=payable.tenant_id,
            legal_entity_id=payable.legal_entity_id,
            batch_id=BATCH_ID,
        )
    elif request.request_amount != payable.final_payable_amount:
        raise FormalActionBlocked("PAYMENT_REQUEST_AMOUNT_CONFLICT", "已有付款申请金额与应付金额不一致。")
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierPayableConfirmation", source_no=payable.payable_confirmation_no,
                   target=request, target_no=request.payment_request_no,
                   before_status=request.status if replay else "", after_status=request.status,
                   amount=request.request_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}")
    return _result(action_code, request, request.payment_request_no, audit, replay=replay,
                   extra={"amount": str(request.request_amount)})


def _transition_request(user, context, reason, action_code):
    request = SupplierPaymentRequest.objects.select_for_update().get(pk=context["source"].pk)
    transitions = {
        ACTION_SUBMIT_PAYMENT_REQUEST: ("draft", "submitted"),
        ACTION_APPROVE_PAYMENT_REQUEST: ("submitted", "approved"),
        ACTION_RELEASE_PAYMENT_REQUEST: ("approved", "payment_pending"),
    }
    before, target = transitions[action_code]
    replay = request.status == target
    if not replay and request.status != before:
        raise FormalActionBlocked("PAYMENT_REQUEST_STATE_INVALID", "付款申请当前状态不允许该动作。")
    if not replay:
        transition_payment_request(request, target, user, reason)
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierPaymentRequest", source_no=request.payment_request_no,
                   target=request, target_no=request.payment_request_no,
                   before_status=target if replay else before, after_status=target,
                   amount=request.request_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}")
    return _result(action_code, request, request.payment_request_no, audit, replay=replay,
                   extra={"amount": str(request.request_amount)})


def _record_payment_status(user, context, reason, action_code):
    request = SupplierPaymentRequest.objects.select_for_update().get(pk=context["source"].pk)
    if request.status != "payment_pending":
        raise FormalActionBlocked("PAYMENT_REQUEST_NOT_PENDING", "付款申请尚未批准并转入待付款处理。")
    payable = context["payable"]
    if request.request_amount > payable.final_payable_amount:
        raise FormalActionBlocked("PAYMENT_AMOUNT_EXCEEDS_PAYABLE", "付款业务状态金额不能超过确认应付金额。")
    record = SupplierPaymentStatusRecord.objects.select_for_update().filter(
        payment_request_no=request.payment_request_no
    ).first()
    replay = bool(record)
    if not record:
        record = create_business_object_with_initial_state(
            model=SupplierPaymentStatusRecord,
            initial_state="draft",
            payment_request_no=request.payment_request_no,
            supplier_id=request.supplier_id,
            supplier_name=request.supplier_name,
            payment_amount=request.request_amount,
            operator=user.get_username(),
            operate_time=timezone.now(),
            remark="业务状态记录；不调用银行、不扣减资金、不写总账。",
            tenant_id=request.tenant_id,
            batch_id=BATCH_ID,
        )
        for state in ("submitted", "approved", "payment_scheduled", "payment_completed"):
            transition_payment_status_record(record, state, user, reason)
    elif record.payment_amount != request.request_amount:
        raise FormalActionBlocked("PAYMENT_STATUS_AMOUNT_CONFLICT", "已有付款状态金额与付款申请金额不一致。")
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierPaymentRequest", source_no=request.payment_request_no,
                   target=record, target_no=request.payment_request_no,
                   before_status=record.status if replay else "", after_status=record.status,
                   amount=record.payment_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}",
                   extra={"businessStatusOnly": True})
    remaining = _money(payable.final_payable_amount - record.payment_amount)
    return _result(action_code, record, request.payment_request_no, audit, replay=replay,
                   extra={"paidAmount": str(record.payment_amount), "remainingAmount": str(remaining),
                          "businessStatusOnly": True})


def _complete_settlement(user, context, reason, action_code):
    record = SupplierPaymentStatusRecord.objects.select_for_update().get(pk=context["source"].pk)
    request = context["request"]
    payable = context["payable"]
    reconciliation = context["reconciliation"]
    if reconciliation.status != "completed" or payable.status != "ready_for_payment_request":
        raise FormalActionBlocked("SETTLEMENT_UPSTREAM_NOT_CONFIRMED", "对账或应付确认尚未完成。")
    if record.status not in {"payment_completed", "settlement_completed"}:
        raise FormalActionBlocked("PAYMENT_STATUS_NOT_COMPLETED", "付款业务状态尚未完成。")
    if _money(record.payment_amount) != _money(payable.final_payable_amount):
        raise FormalActionBlocked("SETTLEMENT_REMAINING_AMOUNT_NOT_ZERO", "未结金额不为零，不能完成供应商结算。")
    completion = SupplierSettlementCompletion.objects.select_for_update().filter(
        payment_request_no=request.payment_request_no
    ).first()
    replay = bool(completion and completion.status == "completed")
    if not completion:
        completion = create_business_object_with_initial_state(
            model=SupplierSettlementCompletion,
            initial_state="pending",
            settlement_no=_number("SSC", record.pk),
            supplier_id=record.supplier_id,
            supplier_name=record.supplier_name,
            reconciliation_no=reconciliation.reconciliation_no,
            payment_request_no=request.payment_request_no,
            completion_date=None,
            performance_update_flag=False,
            tenant_id=record.tenant_id,
            batch_id=BATCH_ID,
        )
    if not replay:
        if record.status == "payment_completed":
            transition_payment_status_record(record, "settlement_completed", user, reason)
        transition_settlement_completion(completion, "completed", user, reason)
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierPaymentStatusRecord", source_no=request.payment_request_no,
                   target=completion, target_no=completion.settlement_no,
                   before_status="completed" if replay else "pending", after_status="completed",
                   amount=record.payment_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}")
    return _result(action_code, completion, completion.settlement_no, audit, replay=replay,
                   extra={"paidAmount": str(record.payment_amount), "remainingAmount": "0.00"})


def _metric_facts(context):
    order = context["order"]
    reconciliation = context["reconciliation"]
    completion = context["source"]
    inspections = list(PurchaseInspection.objects.filter(
        source_receipt__source_purchase_order=order
    ))
    inbounds = list(WarehouseInbound.objects.filter(
        source_inspection__source_receipt__source_purchase_order=order,
        status="completed",
    ))
    qualified = sum((Decimal(row.qualified_quantity) for row in inspections), Decimal("0"))
    inspected = sum((Decimal(row.quantity) for row in inspections), Decimal("0"))
    inbound_date = max((row.inbound_date for row in inbounds), default=None)
    on_time = bool(order.expected_date and inbound_date and inbound_date <= order.expected_date)
    differences = list(SupplierReconciliationDifference.objects.filter(
        reconciliation_no=reconciliation.reconciliation_no
    ))
    nonzero = sum(1 for row in differences if row.difference_amount != 0 or row.difference_quantity != 0)
    amount_difference = sum((abs(row.difference_amount) for row in differences
                             if row.difference_type == "amount_difference"), Decimal("0"))
    accuracy = Decimal("100") if reconciliation.purchase_amount == 0 else max(
        Decimal("0"), Decimal("100") - amount_difference / reconciliation.purchase_amount * Decimal("100")
    )
    quality = Decimal("100") if inspected == 0 else qualified / inspected * Decimal("100")
    return {
        "order": order,
        "reconciliation": reconciliation,
        "completion": completion,
        "delivery": Decimal("100") if on_time else Decimal("0"),
        "quality": _money(quality),
        "price": Decimal("100") if not any(row.difference_type == "price_difference" and row.difference_amount != 0 for row in differences) else Decimal("0"),
        "service": Decimal("100") if nonzero == 0 else Decimal("0"),
        "accuracy": _money(accuracy),
        "differenceCount": nonzero,
    }


def _calculate_supplier_performance(user, context, reason, action_code):
    completion = SupplierSettlementCompletion.objects.select_for_update().get(pk=context["source"].pk)
    if completion.status != "completed":
        raise FormalActionBlocked("SETTLEMENT_NOT_COMPLETED", "供应商结算尚未完成。")
    facts = _metric_facts({**context, "source": completion})
    supplier_id = completion.supplier_id
    period = facts["reconciliation"].period
    metric = SupplierPerformanceMetric.objects.select_for_update().filter(
        supplier_id=supplier_id, period=period, tenant_id=completion.tenant_id
    ).first()
    replay = bool(metric and completion.settlement_no in metric.source_settlement_completion_nos)
    values = [facts["delivery"], facts["quality"], facts["price"], facts["service"], facts["accuracy"]]
    if not metric:
        metric = SupplierPerformanceMetric.objects.create(
            metric_no=f"SPM-{_safe_code(supplier_id)}-{period.replace('-', '')}",
            supplier_id=supplier_id,
            supplier_name=completion.supplier_name,
            period=period,
            delivery_on_time_rate=values[0], quality_pass_rate=values[1],
            price_trend_score=values[2], service_score=values[3],
            reconciliation_accuracy_rate=values[4], overall_score=_money(sum(values) / Decimal("5")),
            source_reconciliation_ids=[facts["reconciliation"].reconciliation_no],
            completed_settlement_count=1, timely_payment_count=1,
            abnormal_settlement_count=0,
            source_settlement_completion_nos=[completion.settlement_no],
            tenant_id=completion.tenant_id, batch_id=BATCH_ID,
        )
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierSettlementCompletion", source_no=completion.settlement_no,
                   target=metric, target_no=metric.metric_no,
                   before_status="calculated" if replay else "", after_status="calculated",
                   amount=facts["reconciliation"].reconciliation_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}",
                   extra={"metricSources": {"purchaseOrderNos": [facts["order"].po_no],
                                             "reconciliationNos": [facts["reconciliation"].reconciliation_no],
                                             "settlementNos": [completion.settlement_no]}})
    return _result(action_code, metric, metric.metric_no, audit, replay=replay,
                   extra={"overallScore": str(metric.overall_score)})


def _calculate_buyer_performance(user, context, reason, action_code):
    completion = SupplierSettlementCompletion.objects.select_for_update().get(pk=context["source"].pk)
    if completion.status != "completed":
        raise FormalActionBlocked("SETTLEMENT_NOT_COMPLETED", "供应商结算尚未完成。")
    facts = _metric_facts({**context, "source": completion})
    order = facts["order"]
    buyer = order.buyer_employee
    buyer_id = buyer.employee_no if buyer else str(order.buyer or "UNKNOWN")
    buyer_name = buyer.full_name if buyer else str(order.buyer or "待确认")
    period = facts["reconciliation"].period
    metric = BuyerPerformanceMetric.objects.select_for_update().filter(
        buyer_id=buyer_id, period=period, tenant_id=completion.tenant_id
    ).first()
    replay = bool(metric and completion.settlement_no in metric.source_settlement_completion_nos)
    on_time = facts["delivery"]
    optimization = Decimal("0")
    response_time = Decimal("0")
    compliance = Decimal("100")
    score = min(Decimal("100"), on_time * Decimal("0.4") + optimization * Decimal("2")
                + (Decimal("10") - response_time) * Decimal("2") + compliance * Decimal("0.3"))
    if not metric:
        metric = BuyerPerformanceMetric.objects.create(
            metric_no=f"BPM-{_safe_code(buyer_id)}-{period.replace('-', '')}",
            buyer_id=buyer_id, buyer_name=buyer_name, period=period,
            purchase_order_count=1, on_time_purchase_rate=on_time,
            price_optimization_rate=optimization, supplier_issue_response_time=response_time,
            process_compliance_rate=compliance, overall_score=_money(score),
            source_purchase_order_ids=[order.po_no],
            difference_responsibility_count=0,
            supplier_issue_count=facts["differenceCount"],
            price_difference_count=0, delivery_delay_count=0 if on_time == 100 else 1,
            payable_confirmation_delay=Decimal("0"), payment_request_accuracy=Decimal("100"),
            payment_request_timeliness_rate=Decimal("100"), settlement_exception_rate=Decimal("0"),
            source_settlement_completion_nos=[completion.settlement_no],
            tenant_id=completion.tenant_id, batch_id=BATCH_ID,
        )
    audit = _audit(user=user, action_code=action_code, context=context,
                   source_type="SupplierSettlementCompletion", source_no=completion.settlement_no,
                   target=metric, target_no=metric.metric_no,
                   before_status="calculated" if replay else "", after_status="calculated",
                   amount=facts["reconciliation"].reconciliation_amount,
                   reason=f"{reason}{' / 幂等重放' if replay else ''}",
                   extra={"metricSources": {"purchaseOrderNos": [order.po_no],
                                             "reconciliationNos": [facts["reconciliation"].reconciliation_no],
                                             "settlementNos": [completion.settlement_no]}})
    return _result(action_code, metric, metric.metric_no, audit, replay=replay,
                   extra={"buyerId": buyer_id, "buyerName": buyer_name,
                          "overallScore": str(metric.overall_score)})


def formal_chain_readback(order_id):
    """Read-only same-object projection used by API, page diagnostics and acceptance."""
    order = PurchaseOrder.objects.filter(pk=order_id).first()
    if not order:
        raise FormalActionBlocked("PURCHASE_ORDER_NOT_FOUND", "采购订单不存在。", 404)
    reconciliation = next((row for row in SupplierReconciliation.objects.all()
                           if order.po_no in (row.purchase_order_ids or [])), None)
    differences = list(SupplierReconciliationDifference.objects.filter(
        reconciliation_no=reconciliation.reconciliation_no
    )) if reconciliation else []
    payable = SupplierPayableConfirmation.objects.filter(
        reconciliation_no=reconciliation.reconciliation_no
    ).first() if reconciliation else None
    request = SupplierPaymentRequest.objects.filter(
        payable_confirmation_no=payable.payable_confirmation_no
    ).first() if payable else None
    payment = SupplierPaymentStatusRecord.objects.filter(
        payment_request_no=request.payment_request_no
    ).first() if request else None
    settlement = SupplierSettlementCompletion.objects.filter(
        payment_request_no=request.payment_request_no
    ).first() if request else None
    supplier_metric = next((row for row in SupplierPerformanceMetric.objects.all()
                            if settlement and settlement.settlement_no in (row.source_settlement_completion_nos or [])), None)
    buyer_metric = next((row for row in BuyerPerformanceMetric.objects.all()
                         if settlement and settlement.settlement_no in (row.source_settlement_completion_nos or [])), None)
    source_nos = {value for value in [
        order.po_no,
        reconciliation.reconciliation_no if reconciliation else None,
        payable.payable_confirmation_no if payable else None,
        request.payment_request_no if request else None,
        settlement.settlement_no if settlement else None,
    ] if value}
    audits = [row for row in SupplierSettlementActionAudit.objects.select_related("operator")
              .filter(tenant_id=str(order.company_id)).order_by("timestamp", "pk")
              if row.source_object_no in source_nos]
    diff_values = {row.difference_type: row for row in differences}
    return {
        "formalVersion": FORMAL_VERSION,
        "purchaseOrder": {"id": order.pk, "no": order.po_no, "status": order.status,
                          "amount": str(_money(order.total_amount)), "supplier": order.supplier.name},
        "reconciliation": ({"id": reconciliation.pk, "no": reconciliation.reconciliation_no,
                            "status": reconciliation.status, "amount": str(reconciliation.reconciliation_amount),
                            "sourceRelations": {
                                "purchaseOrders": reconciliation.purchase_order_ids,
                                "receipts": reconciliation.receipt_ids,
                                "inspections": reconciliation.inspection_ids,
                                "inbounds": reconciliation.warehouse_receipt_ids,
                                "inventoryTransactions": reconciliation.inventory_transaction_ids,
                            }} if reconciliation else None),
        "differences": {
            "quantity": str(diff_values.get("quantity_difference").difference_quantity) if diff_values.get("quantity_difference") else None,
            "price": str(diff_values.get("price_difference").difference_amount) if diff_values.get("price_difference") else None,
            "amount": str(diff_values.get("amount_difference").difference_amount) if diff_values.get("amount_difference") else None,
            "records": [{"id": row.pk, "no": row.difference_no, "type": row.difference_type,
                         "status": row.status} for row in differences],
        },
        "payable": ({"id": payable.pk, "no": payable.payable_confirmation_no,
                     "status": payable.status, "amount": str(payable.final_payable_amount)} if payable else None),
        "paymentRequest": ({"id": request.pk, "no": request.payment_request_no,
                            "status": request.status, "amount": str(request.request_amount)} if request else None),
        "paymentStatus": ({"id": payment.pk, "status": payment.status,
                           "paidAmount": str(payment.payment_amount),
                           "remainingAmount": str(_money(payable.final_payable_amount - payment.payment_amount))} if payment and payable else None),
        "settlement": ({"id": settlement.pk, "no": settlement.settlement_no,
                        "status": settlement.status} if settlement else None),
        "supplierPerformance": ({"id": supplier_metric.pk, "no": supplier_metric.metric_no,
                                 "overallScore": str(supplier_metric.overall_score)} if supplier_metric else None),
        "buyerPerformance": ({"id": buyer_metric.pk, "no": buyer_metric.metric_no,
                              "buyer": buyer_metric.buyer_name,
                              "overallScore": str(buyer_metric.overall_score)} if buyer_metric else None),
        "audits": [{
            "auditNo": row.action_no, "actionCode": row.action_code,
            "operator": row.operator.username, "employee": row.evidence.get("employee"),
            "position": row.evidence.get("position"), "responsibility": row.evidence.get("responsibility"),
            "permission": row.evidence.get("authorization", {}).get("permissionCodes", []),
            "authorizationResult": row.authorization_result,
            "source": {"type": row.source_object_type, "no": row.source_object_no},
            "target": {"type": row.object_type, "id": row.object_id, "no": row.object_no},
            "amount": str(row.amount), "beforeStatus": row.before_status,
            "afterStatus": row.after_status, "at": row.timestamp.isoformat(),
        } for row in audits],
        "safety": {"paymentExecutionWriteCount": 0, "bankSendWriteCount": 0,
                   "fundDeductionCount": 0, "generalLedgerWriteCount": 0},
    }
