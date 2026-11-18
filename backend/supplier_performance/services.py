from decimal import Decimal
from datetime import date
import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    BuyerPerformanceMetric,
    SupplierPerformanceMetric,
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierPaymentStatusRecord,
    SupplierSettlementCompletion,
    SupplierSettlementActionAudit,
    SupplierReconciliation,
    SupplierReconciliationConfirmation,
    SupplierReconciliationDifference,
)


VERSION = "V1.14.2.8.4.8.1"
V82_VERSION = "V1.14.2.8.4.8.2"
V83_VERSION = "V1.14.2.8.4.8.3"
V831_VERSION = "V1.14.2.8.4.8.3.1.1"
V84_VERSION = "V1.14.2.8.4.8.4"
TENANT_ID = "tenant-canary-demo"
BATCH_ID = "SUPPLIER-SETTLEMENT-V81"
ALLOWED_TRANSITIONS = {
    ("draft", "internal_review"),
    ("internal_review", "supplier_confirming"),
    ("supplier_confirming", "completed"),
}
STATUS_LABELS = dict(SupplierReconciliation.Status.choices)
DIFFERENCE_TRANSITIONS = {
    ("draft", "analyzing"),
    ("analyzing", "responsibility_confirmed"),
    ("responsibility_confirmed", "supplier_communicating"),
    ("supplier_communicating", "closed"),
}
CONFIRMATION_TRANSITIONS = {
    ("waiting_supplier", "supplier_confirmed"),
    ("supplier_confirmed", "internal_verified"),
    ("internal_verified", "completed"),
}
PAYABLE_CONFIRMATION_TRANSITIONS = {
    ("draft", "internal_review"),
    ("internal_review", "confirmed"),
    ("confirmed", "ready_for_payment_request"),
}
PAYMENT_REQUEST_TRANSITIONS = {
    ("draft", "submitted"),
    ("submitted", "approved"),
    ("approved", "payment_pending"),
    ("submitted", "draft"),
}
PAYMENT_STATUS_TRANSITIONS = {
    ("draft", "submitted"),
    ("submitted", "approved"),
    ("approved", "payment_scheduled"),
    ("payment_scheduled", "payment_completed"),
    ("payment_completed", "settlement_completed"),
}
SETTLEMENT_COMPLETION_TRANSITIONS = {("pending", "completed")}

V831_ACTIONS = {
    "SCM_PAYABLE_SUBMIT_REVIEW": {
        "model": SupplierPayableConfirmation,
        "objectType": "SupplierPayableConfirmation",
        "moduleCode": "supplier-payable-confirmation",
        "source": "draft",
        "target": "internal_review",
        "role": "scm_payable_buyer",
        "roleLabel": "采购员",
        "testActor": "v831-payable-buyer",
        "label": "提交应付确认审核",
        "numberField": "payable_confirmation_no",
    },
    "SCM_PAYABLE_APPROVE": {
        "model": SupplierPayableConfirmation,
        "objectType": "SupplierPayableConfirmation",
        "moduleCode": "supplier-payable-confirmation",
        "source": "internal_review",
        "target": "confirmed",
        "role": "scm_payable_supervisor",
        "roleLabel": "采购主管",
        "testActor": "v831-payable-supervisor",
        "label": "确认应付结果",
        "numberField": "payable_confirmation_no",
    },
    "SCM_PAYABLE_CREATE_PAYMENT_REQUEST": {
        "model": SupplierPayableConfirmation,
        "objectType": "SupplierPayableConfirmation",
        "moduleCode": "supplier-payable-confirmation",
        "source": "confirmed",
        "target": "ready_for_payment_request",
        "role": "scm_payable_supervisor",
        "roleLabel": "采购主管",
        "testActor": "v831-payable-supervisor",
        "label": "生成付款申请资格",
        "numberField": "payable_confirmation_no",
    },
    "SCM_PAYMENT_REQUEST_SUBMIT": {
        "model": SupplierPaymentRequest,
        "objectType": "SupplierPaymentRequest",
        "moduleCode": "supplier-payment-request",
        "source": "draft",
        "target": "submitted",
        "role": "scm_payment_request_applicant",
        "roleLabel": "申请人",
        "testActor": "v831-payment-applicant",
        "label": "提交付款申请",
        "numberField": "payment_request_no",
    },
    "SCM_PAYMENT_REQUEST_APPROVE": {
        "model": SupplierPaymentRequest,
        "objectType": "SupplierPaymentRequest",
        "moduleCode": "supplier-payment-request",
        "source": "submitted",
        "target": "approved",
        "role": "scm_payment_request_owner",
        "roleLabel": "负责人",
        "testActor": "v831-payment-owner",
        "label": "审批付款申请",
        "numberField": "payment_request_no",
    },
    "SCM_PAYMENT_REQUEST_RETURN": {
        "model": SupplierPaymentRequest,
        "objectType": "SupplierPaymentRequest",
        "moduleCode": "supplier-payment-request",
        "source": "submitted",
        "target": "draft",
        "role": "scm_payment_request_owner",
        "roleLabel": "负责人",
        "testActor": "v831-payment-owner",
        "label": "退回付款申请",
        "numberField": "payment_request_no",
    },
}


def transition_reconciliation(obj, target_state, operator, reason):
    return transition_business_object(
        business_object=obj,
        object_type="SupplierReconciliation",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_reconciliation_state_transition",
        operator=operator,
        reason=reason,
        audit_reference=f"V81-{obj.reconciliation_no}-{obj.version}-{target_state}",
        allowed_transitions=ALLOWED_TRANSITIONS,
    )


def transition_difference(obj, target_state, operator, reason):
    return transition_business_object(
        business_object=obj,
        object_type="SupplierReconciliationDifference",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_reconciliation_difference_transition",
        operator=operator,
        reason=reason,
        audit_reference=f"V82-{obj.difference_no}-{obj.version}-{target_state}",
        allowed_transitions=DIFFERENCE_TRANSITIONS,
    )


def transition_confirmation(obj, target_state, operator, reason):
    return transition_business_object(
        business_object=obj,
        object_type="SupplierReconciliationConfirmation",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_reconciliation_confirmation_transition",
        operator=operator,
        reason=reason,
        audit_reference=f"V82-{obj.confirmation_no}-{obj.version}-{target_state}",
        allowed_transitions=CONFIRMATION_TRANSITIONS,
    )


def transition_payable_confirmation(
    obj, target_state, operator, reason, audit_reference=None
):
    return transition_business_object(
        business_object=obj,
        object_type="SupplierPayableConfirmation",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_payable_confirmation_state_transition",
        operator=operator,
        reason=reason,
        audit_reference=(
            audit_reference
            or f"V83-{obj.payable_confirmation_no}-{obj.version}-{target_state}"
        ),
        allowed_transitions=PAYABLE_CONFIRMATION_TRANSITIONS,
    )


def transition_payment_request(
    obj, target_state, operator, reason, audit_reference=None
):
    return transition_business_object(
        business_object=obj,
        object_type="SupplierPaymentRequest",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_payment_request_state_transition",
        operator=operator,
        reason=reason,
        audit_reference=(
            audit_reference
            or f"V83-{obj.payment_request_no}-{obj.version}-{target_state}"
        ),
        allowed_transitions=PAYMENT_REQUEST_TRANSITIONS,
    )


def transition_payment_status_record(obj, target_state, operator, reason):
    transition = transition_business_object(
        business_object=obj,
        object_type="SupplierPaymentStatusRecord",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_payment_status_transition",
        operator=operator,
        reason=reason,
        audit_reference=f"V84-{obj.payment_request_no}-{obj.version}-{target_state}",
        allowed_transitions=PAYMENT_STATUS_TRANSITIONS,
    )
    obj.operator = operator.get_username()
    obj.operate_time = timezone.now()
    obj.remark = reason
    obj.save(update_fields=["operator", "operate_time", "remark", "updated_at"])
    return transition


def transition_settlement_completion(obj, target_state, operator, reason):
    transition = transition_business_object(
        business_object=obj,
        object_type="SupplierSettlementCompletion",
        source_state=obj.status,
        target_state=target_state,
        action_code="supplier_settlement_completion_transition",
        operator=operator,
        reason=reason,
        audit_reference=f"V84-{obj.settlement_no}-{obj.version}-{target_state}",
        allowed_transitions=SETTLEMENT_COMPLETION_TRANSITIONS,
    )
    obj.completion_date = date.today()
    obj.performance_update_flag = True
    obj.save(update_fields=["completion_date", "performance_update_flag", "updated_at"])
    return transition


def available_v831_actions(object_type, status):
    actions = []
    for code, definition in V831_ACTIONS.items():
        if (
            definition["objectType"] != object_type
            or definition["source"] != status
        ):
            continue
        action = {
            "actionCode": code,
            "actionLabel": definition["label"],
            "role": definition["role"],
            "roleLabel": definition["roleLabel"],
            "sourceStatus": definition["source"],
            "targetStatus": definition["target"],
            "registrySource": "PCE Business Action Registry",
        }
        if getattr(
            settings, "PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED", False
        ):
            action["testActor"] = definition["testActor"]
        actions.append(action)
    return actions


def serialize_v831_audits(object_type, object_id):
    return [
        {
            "actionNo": row.action_no,
            "actionCode": row.action_code,
            "actionLabel": V831_ACTIONS.get(
                row.action_code, {}
            ).get("label", row.action_code),
            "operator": row.operator.get_username(),
            "role": row.role,
            "roleLabel": V831_ACTIONS.get(
                row.action_code, {}
            ).get("roleLabel", row.role),
            "beforeStatus": row.before_status,
            "afterStatus": row.after_status,
            "timestamp": row.timestamp.isoformat(),
            "auditReference": f"SupplierSettlementActionAudit:{row.pk}",
        }
        for row in SupplierSettlementActionAudit.objects.filter(
            object_type=object_type, object_id=object_id
        ).select_related("operator").order_by("timestamp", "pk")
    ]


def inspect_v831_action(*, user, action_code, object_id):
    from workflow_runtime.action_permissions import ActionPermissionValidator

    definition = V831_ACTIONS.get(action_code)
    if not definition:
        raise ValueError("WORKFLOW_ACTION_NOT_REGISTERED")
    obj = definition["model"].objects.get(pk=object_id)
    decision = ActionPermissionValidator().evaluate(
        user=user,
        module_code=definition["moduleCode"],
        action_code=action_code,
        object_ids=[obj.pk],
        selection_count=1,
        requested_legal_entity_id=obj.legal_entity_id,
    )
    if not decision["granted"]:
        raise PermissionError(decision["decisionCode"])
    if obj.status != definition["source"]:
        raise ValueError("WORKFLOW_ACTION_STATUS_MISMATCH")
    return definition, obj, decision


@transaction.atomic
def execute_v831_action(*, user, action_code, object_id, reason):
    definition, unlocked_obj, _ = inspect_v831_action(
        user=user, action_code=action_code, object_id=object_id
    )
    obj = definition["model"].objects.select_for_update().get(
        pk=unlocked_obj.pk
    )
    if obj.status != definition["source"]:
        raise ValueError("WORKFLOW_ACTION_STATUS_MISMATCH")
    object_no = getattr(obj, definition["numberField"])
    audit = SupplierSettlementActionAudit.objects.create(
        action_no=f"SSA-V831-{uuid.uuid4().hex.upper()}",
        action_code=action_code,
        operator=user,
        role=definition["role"],
        object_type=definition["objectType"],
        object_id=obj.pk,
        object_no=object_no,
        before_status=obj.status,
        after_status=definition["target"],
        reason=str(reason or definition["label"]).strip(),
        tenant_id=obj.tenant_id,
        legal_entity_id=obj.legal_entity_id,
    )
    if definition["objectType"] == "SupplierPayableConfirmation":
        transition_payable_confirmation(
            obj,
            definition["target"],
            user,
            audit.reason,
            audit_reference=f"SupplierSettlementActionAudit:{audit.pk}",
        )
    else:
        transition_payment_request(
            obj,
            definition["target"],
            user,
            audit.reason,
            audit_reference=f"SupplierSettlementActionAudit:{audit.pk}",
        )
    obj.refresh_from_db()
    return {
        "actionNo": audit.action_no,
        "actionCode": action_code,
        "operator": user.get_username(),
        "role": definition["role"],
        "beforeStatus": audit.before_status,
        "afterStatus": obj.status,
        "timestamp": audit.timestamp.isoformat(),
        "auditReference": f"SupplierSettlementActionAudit:{audit.pk}",
    }


@transaction.atomic
def ensure_demo_data(operator):
    suppliers = [
        ("SUP-001", "精工材料", Decimal("128000.00"), "completed"),
        ("SUP-002", "华东机电", Decimal("96500.00"), "supplier_confirming"),
        ("SUP-003", "卓越包装", Decimal("53200.00"), "internal_review"),
        ("SUP-004", "新源化工", Decimal("41800.00"), "draft"),
    ]
    for index, (supplier_id, supplier_name, amount, final_state) in enumerate(suppliers, 1):
        no = f"SR-V81-202607-{index:03d}"
        obj = SupplierReconciliation.objects.filter(reconciliation_no=no).first()
        created = obj is None
        if not obj:
            obj = create_business_object_with_initial_state(
                model=SupplierReconciliation,
                initial_state="draft",
                reconciliation_no=no,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                period="2026-07",
                purchase_order_ids=[f"PO-V81-{index:03d}-1", f"PO-V81-{index:03d}-2"],
                receipt_ids=[f"REC-V81-{index:03d}-1"],
                inspection_ids=[f"QI-V81-{index:03d}-1"],
                warehouse_receipt_ids=[f"WHR-V81-{index:03d}-1"],
                purchase_amount=amount,
                received_amount=amount - Decimal("500.00"),
                qualified_amount=amount - Decimal("800.00"),
                reconciliation_amount=amount - Decimal("800.00"),
                tenant_id=TENANT_ID,
                batch_id=BATCH_ID,
            )
        if created:
            chain = ["internal_review", "supplier_confirming", "completed"]
            for state in chain[: chain.index(final_state) + 1] if final_state != "draft" else []:
                transition_reconciliation(obj, state, operator, f"V81 demo transition to {state}")

    buyer_rows = [
        ("BUYER-001", "张敏", 16, "93.75", "8.20", "2.50", "98.00"),
        ("BUYER-002", "李强", 13, "92.31", "6.80", "3.20", "96.00"),
        ("BUYER-003", "王琳", 11, "90.91", "7.40", "2.80", "97.00"),
    ]
    for index, (buyer_id, buyer_name, count, on_time, optimization, response, compliance) in enumerate(buyer_rows, 1):
        score = (Decimal(on_time) * Decimal("0.4") + Decimal(optimization) * Decimal("2")
                 + (Decimal("10") - Decimal(response)) * Decimal("2") + Decimal(compliance) * Decimal("0.3"))
        BuyerPerformanceMetric.objects.get_or_create(
            buyer_id=buyer_id, period="2026-07", tenant_id=TENANT_ID,
            defaults={
                "metric_no": f"BPM-V81-{index:03d}", "buyer_name": buyer_name,
                "purchase_order_count": count, "on_time_purchase_rate": on_time,
                "price_optimization_rate": optimization, "supplier_issue_response_time": response,
                "process_compliance_rate": compliance, "overall_score": min(score, Decimal("100")),
                "source_purchase_order_ids": [f"PO-{buyer_id}-{i}" for i in range(1, count + 1)],
                "batch_id": BATCH_ID,
            },
        )
    supplier_rows = [
        ("SUP-001", "精工材料", "96", "98", "91", "95", "99"),
        ("SUP-002", "华东机电", "94", "96", "90", "93", "97"),
        ("SUP-003", "卓越包装", "92", "95", "94", "96", "98"),
        ("SUP-004", "新源化工", "90", "93", "89", "92", "95"),
    ]
    for index, row in enumerate(supplier_rows, 1):
        supplier_id, name, delivery, quality, price, service, accuracy = row
        values = [Decimal(delivery), Decimal(quality), Decimal(price), Decimal(service), Decimal(accuracy)]
        SupplierPerformanceMetric.objects.get_or_create(
            supplier_id=supplier_id, period="2026-07", tenant_id=TENANT_ID,
            defaults={
                "metric_no": f"SPM-V81-{index:03d}", "supplier_name": name,
                "delivery_on_time_rate": values[0], "quality_pass_rate": values[1],
                "price_trend_score": values[2], "service_score": values[3],
                "reconciliation_accuracy_rate": values[4],
                "overall_score": sum(values) / Decimal("5"),
                "source_reconciliation_ids": [f"SR-V81-202607-{index:03d}"],
                "batch_id": BATCH_ID,
            },
        )


def base_facts(record_count, fact_type, api_url, **extra):
    return {
        "factType": fact_type, "factSource": "server", "recordCount": record_count,
        "actionCount": 4, "dangerActionCount": 0, "businessProgressWriteCount": 0,
        "downstreamObjectCount": 0, "paymentExecutionWriteCount": 0,
        "bankSendWriteCount": 0, "financialImpactWriteCount": 0,
        "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
        "factLoadStatus": "success", "apiUrl": api_url, "httpStatus": 200,
        "tenantId": TENANT_ID, "batchId": BATCH_ID, **extra,
    }


@transaction.atomic
def ensure_v82_demo_data(operator):
    ensure_demo_data(operator)
    difference_rows = [
        ("SUP-001", "精工材料", "BUYER-001", "张敏", "quantity_difference", "supplier", "1250.00", "20", "closed"),
        ("SUP-002", "华东机电", "BUYER-002", "李强", "quality_difference", "quality", "2800.00", "8", "supplier_communicating"),
        ("SUP-003", "卓越包装", "BUYER-003", "王琳", "price_difference", "buyer", "1600.00", "0", "responsibility_confirmed"),
        ("SUP-004", "新源化工", "BUYER-001", "张敏", "delivery_difference", "supplier", "900.00", "0", "analyzing"),
        ("SUP-001", "精工材料", "BUYER-002", "李强", "other_difference", "unknown", "500.00", "2", "draft"),
        ("SUP-002", "华东机电", "BUYER-003", "王琳", "price_difference", "supplier", "1100.00", "0", "closed"),
        ("SUP-003", "卓越包装", "BUYER-001", "张敏", "delivery_difference", "warehouse", "700.00", "4", "supplier_communicating"),
        ("SUP-004", "新源化工", "BUYER-002", "李强", "quantity_difference", "buyer", "450.00", "12", "responsibility_confirmed"),
    ]
    status_chain = ["analyzing", "responsibility_confirmed", "supplier_communicating", "closed"]
    for index, row in enumerate(difference_rows, 1):
        supplier_id, supplier_name, buyer_id, buyer_name, difference_type, responsibility, amount, quantity, final_state = row
        difference_no = f"SRD-V82-202607-{index:03d}"
        obj = SupplierReconciliationDifference.objects.filter(difference_no=difference_no).first()
        created = obj is None
        if created:
            obj = create_business_object_with_initial_state(
                model=SupplierReconciliationDifference,
                initial_state="draft",
                difference_no=difference_no,
                reconciliation_no=f"SR-V81-202607-{((index - 1) % 4) + 1:03d}",
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                buyer_id=buyer_id,
                buyer_name=buyer_name,
                difference_type=difference_type,
                difference_amount=Decimal(amount),
                difference_quantity=Decimal(quantity),
                responsibility_type=responsibility,
                occurred_at=date(2026, 7, min(index + 2, 28)),
                source_object_refs={
                    "purchaseOrder": f"PO-V81-{((index - 1) % 4) + 1:03d}-1",
                    "receipt": f"REC-V81-{((index - 1) % 4) + 1:03d}-1",
                    "inspection": f"QI-V81-{((index - 1) % 4) + 1:03d}-1",
                    "warehouseReceipt": f"WHR-V81-{((index - 1) % 4) + 1:03d}-1",
                },
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V82",
            )
        if created and final_state != "draft":
            for state in status_chain[:status_chain.index(final_state) + 1]:
                transition_difference(obj, state, operator, f"V82 demo transition to {state}")

    confirmation_rows = [
        (1, "accepted", "已认可差异处理结果", "completed"),
        (2, "disputed", "对质量责任仍需补充材料", "internal_verified"),
        (7, "accepted", "接受仓库复核结论", "supplier_confirmed"),
        (4, "pending", "等待供应商回复", "waiting_supplier"),
    ]
    confirmation_chain = ["supplier_confirmed", "internal_verified", "completed"]
    for index, (difference_index, response, comment, final_state) in enumerate(confirmation_rows, 1):
        difference = SupplierReconciliationDifference.objects.get(
            difference_no=f"SRD-V82-202607-{difference_index:03d}"
        )
        confirmation_no = f"SRC-V82-202607-{index:03d}"
        obj = SupplierReconciliationConfirmation.objects.filter(confirmation_no=confirmation_no).first()
        created = obj is None
        if created:
            obj = create_business_object_with_initial_state(
                model=SupplierReconciliationConfirmation,
                initial_state="waiting_supplier",
                confirmation_no=confirmation_no,
                difference_no=difference.difference_no,
                supplier_id=difference.supplier_id,
                supplier_response=response,
                supplier_comment=comment,
                confirmed_by=difference.supplier_name if final_state != "waiting_supplier" else "",
                confirmed_at=timezone.now() if final_state != "waiting_supplier" else None,
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V82",
            )
        if created and final_state != "waiting_supplier":
            for state in confirmation_chain[:confirmation_chain.index(final_state) + 1]:
                transition_confirmation(obj, state, operator, f"V82 demo transition to {state}")

    for metric in BuyerPerformanceMetric.objects.all():
        owned = SupplierReconciliationDifference.objects.filter(buyer_id=metric.buyer_id)
        metric.difference_responsibility_count = owned.filter(responsibility_type="buyer").count()
        metric.supplier_issue_count = owned.filter(responsibility_type="supplier").count()
        metric.price_difference_count = owned.filter(difference_type="price_difference").count()
        metric.delivery_delay_count = owned.filter(difference_type="delivery_difference").count()
        metric.save(update_fields=[
            "difference_responsibility_count", "supplier_issue_count",
            "price_difference_count", "delivery_delay_count",
        ])


@transaction.atomic
def ensure_v83_demo_data(operator):
    ensure_v82_demo_data(operator)
    reconciliations = list(SupplierReconciliation.objects.order_by("reconciliation_no"))
    deductions = [Decimal("1250.00"), Decimal("2800.00"), Decimal("1600.00"), Decimal("900.00")]
    payable_chain = ["internal_review", "confirmed", "ready_for_payment_request"]
    payables = []
    for index, reconciliation in enumerate(reconciliations, 1):
        payable_no = f"SPC-V83-202607-{index:03d}"
        obj = SupplierPayableConfirmation.objects.filter(
            payable_confirmation_no=payable_no
        ).first()
        created = obj is None
        if created:
            final_amount = reconciliation.qualified_amount - deductions[index - 1]
            obj = create_business_object_with_initial_state(
                model=SupplierPayableConfirmation,
                initial_state="draft",
                payable_confirmation_no=payable_no,
                supplier_id=reconciliation.supplier_id,
                supplier_name=reconciliation.supplier_name,
                reconciliation_no=reconciliation.reconciliation_no,
                period=reconciliation.period,
                confirmed_amount=reconciliation.reconciliation_amount,
                qualified_amount=reconciliation.qualified_amount,
                deduction_amount=deductions[index - 1],
                final_payable_amount=final_amount,
                source_object_refs={
                    "reconciliation": reconciliation.reconciliation_no,
                    "purchaseOrders": reconciliation.purchase_order_ids,
                    "warehouseReceipts": reconciliation.warehouse_receipt_ids,
                    "closedDifferences": list(
                        SupplierReconciliationDifference.objects.filter(
                            reconciliation_no=reconciliation.reconciliation_no,
                            status="closed",
                        ).values_list("difference_no", flat=True)
                    ),
                },
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V83",
            )
        target_state = "ready_for_payment_request" if index <= 3 else "internal_review"
        if created:
            for state in payable_chain[:payable_chain.index(target_state) + 1]:
                transition_payable_confirmation(obj, state, operator, f"V83 demo transition to {state}")
        payables.append(obj)

    request_chain = ["submitted", "approved", "payment_pending"]
    target_states = ["payment_pending", "approved", "submitted"]
    for index, payable in enumerate(payables[:3], 1):
        request_no = f"SPR-V83-202607-{index:03d}"
        obj = SupplierPaymentRequest.objects.filter(payment_request_no=request_no).first()
        created = obj is None
        if created:
            obj = create_business_object_with_initial_state(
                model=SupplierPaymentRequest,
                initial_state="draft",
                payment_request_no=request_no,
                payable_confirmation_no=payable.payable_confirmation_no,
                supplier_id=payable.supplier_id,
                supplier_name=payable.supplier_name,
                period=payable.period,
                request_amount=payable.final_payable_amount,
                request_reason="供应商对账完成后的付款申请，仅进入待付款状态",
                requested_by=operator,
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V83",
            )
        if created:
            target_state = target_states[index - 1]
            for state in request_chain[:request_chain.index(target_state) + 1]:
                transition_payment_request(obj, state, operator, f"V83 demo transition to {state}")

    delay_values = [Decimal("1.50"), Decimal("2.00"), Decimal("0.80")]
    accuracy_values = [Decimal("99.00"), Decimal("97.00"), Decimal("98.00")]
    for index, metric in enumerate(BuyerPerformanceMetric.objects.order_by("buyer_id")):
        metric.payable_confirmation_delay = delay_values[index]
        metric.payment_request_accuracy = accuracy_values[index]
        metric.save(update_fields=["payable_confirmation_delay", "payment_request_accuracy"])


@transaction.atomic
def ensure_v831_demo_data():
    from django.contrib.auth import get_user_model
    from system.models import Permission, Role, RolePermission
    from workflow_runtime.action_permissions import required_permission_code
    from workflow_runtime.models import UserOrganizationRoleAuthority

    actor_rows = [
        ("v831-payable-buyer", "V83.1 采购员", "scm_payable_buyer"),
        ("v831-payable-supervisor", "V83.1 采购主管", "scm_payable_supervisor"),
        ("v831-payment-applicant", "V83.1 付款申请人", "scm_payment_request_applicant"),
        ("v831-payment-owner", "V83.1 付款负责人", "scm_payment_request_owner"),
    ]
    users = {}
    user_model = get_user_model()
    for username, real_name, role_code in actor_rows:
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={
                "real_name": real_name,
                "company_id": 1,
                "email": f"{username}@example.invalid",
                "is_active": True,
            },
        )
        users[role_code] = user
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": real_name, "description": "V83.1 供应商结算工作流角色"},
        )
        UserOrganizationRoleAuthority.objects.get_or_create(
            user=user,
            role_code=role_code,
            legal_entity_id="LE-CANARY-001",
            defaults={
                "department_id": "SCM",
                "active": True,
                "version": 1,
                "business_hash": f"V831-{role_code}",
            },
        )
        for action_code, definition in V831_ACTIONS.items():
            if definition["role"] != role_code:
                continue
            permission, _ = Permission.objects.get_or_create(
                code=required_permission_code(definition["moduleCode"], action_code),
                defaults={
                    "name": definition["label"],
                    "module": definition["moduleCode"],
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=permission)

    ensure_v83_demo_data(users["scm_payable_buyer"])
    reconciliations = list(SupplierReconciliation.objects.order_by("reconciliation_no"))
    demo_states = [
        (5, "draft", Decimal("500.00")),
        (6, "confirmed", Decimal("600.00")),
        (7, "ready_for_payment_request", Decimal("700.00")),
    ]
    payable_chain = ["internal_review", "confirmed", "ready_for_payment_request"]
    created_payables = {}
    for index, target_state, deduction in demo_states:
        reconciliation = reconciliations[(index - 1) % len(reconciliations)]
        payable_no = f"SPC-V831-202607-{index:03d}"
        obj = SupplierPayableConfirmation.objects.filter(
            payable_confirmation_no=payable_no
        ).first()
        created = obj is None
        if created:
            obj = create_business_object_with_initial_state(
                model=SupplierPayableConfirmation,
                initial_state="draft",
                payable_confirmation_no=payable_no,
                supplier_id=reconciliation.supplier_id,
                supplier_name=reconciliation.supplier_name,
                reconciliation_no=reconciliation.reconciliation_no,
                period=reconciliation.period,
                confirmed_amount=reconciliation.reconciliation_amount,
                qualified_amount=reconciliation.qualified_amount,
                deduction_amount=deduction,
                final_payable_amount=reconciliation.qualified_amount - deduction,
                source_object_refs={
                    "reconciliation": reconciliation.reconciliation_no,
                    "workflowCanary": "V83.1",
                },
                tenant_id=TENANT_ID,
                legal_entity_id="LE-CANARY-001",
                batch_id="SUPPLIER-SETTLEMENT-V831",
            )
        if created and target_state != "draft":
            for state in payable_chain[:payable_chain.index(target_state) + 1]:
                transition_payable_confirmation(
                    obj, state, users["scm_payable_buyer"], f"V83.1 seed to {state}"
                )
        created_payables[index] = obj

    source = created_payables[7]
    request_no = "SPR-V831-202607-004"
    if not SupplierPaymentRequest.objects.filter(payment_request_no=request_no).exists():
        create_business_object_with_initial_state(
            model=SupplierPaymentRequest,
            initial_state="draft",
            payment_request_no=request_no,
            payable_confirmation_no=source.payable_confirmation_no,
            supplier_id=source.supplier_id,
            supplier_name=source.supplier_name,
            period=source.period,
            request_amount=source.final_payable_amount,
            request_reason="V83.1 工作流动作验收付款申请，不执行付款",
            requested_by=users["scm_payment_request_applicant"].get_username(),
            tenant_id=TENANT_ID,
            legal_entity_id="LE-CANARY-001",
            batch_id="SUPPLIER-SETTLEMENT-V831",
        )
    return users


@transaction.atomic
def ensure_v84_demo_data():
    users = ensure_v831_demo_data()
    operator = users["scm_payment_request_owner"]
    requests = list(SupplierPaymentRequest.objects.order_by("payment_request_no")[:4])
    target_states = [
        "settlement_completed",
        "payment_completed",
        "payment_scheduled",
        "approved",
    ]
    status_labels = dict(SupplierPaymentStatusRecord.Status.choices)
    state_chain = [
        "submitted",
        "approved",
        "payment_scheduled",
        "payment_completed",
        "settlement_completed",
    ]
    records = []
    for index, payment_request in enumerate(requests):
        record = SupplierPaymentStatusRecord.objects.filter(
            payment_request_no=payment_request.payment_request_no
        ).first()
        created = record is None
        if created:
            record = create_business_object_with_initial_state(
                model=SupplierPaymentStatusRecord,
                initial_state="draft",
                payment_request_no=payment_request.payment_request_no,
                supplier_id=payment_request.supplier_id,
                supplier_name=payment_request.supplier_name,
                payment_amount=payment_request.request_amount,
                operator=operator.get_username(),
                operate_time=timezone.now(),
                remark="V84 供应商付款业务状态初始化；不执行付款",
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V84",
            )
        target = target_states[index]
        if created:
            for state in state_chain[:state_chain.index(target) + 1]:
                transition_payment_status_record(
                    record,
                    state,
                    operator,
                    f"V84 业务状态推进至{status_labels[state]}",
                )
        records.append(record)

    reconciliations = {
        item.supplier_id: item
        for item in SupplierReconciliation.objects.order_by("reconciliation_no")
    }
    for index, record in enumerate(records[:2], 1):
        completion = SupplierSettlementCompletion.objects.filter(
            payment_request_no=record.payment_request_no
        ).first()
        created = completion is None
        reconciliation = reconciliations.get(record.supplier_id)
        if created:
            completion = create_business_object_with_initial_state(
                model=SupplierSettlementCompletion,
                initial_state="pending",
                settlement_no=f"SSC-V84-202607-{index:03d}",
                supplier_id=record.supplier_id,
                supplier_name=record.supplier_name,
                reconciliation_no=(
                    reconciliation.reconciliation_no if reconciliation else ""
                ),
                payment_request_no=record.payment_request_no,
                completion_date=None,
                performance_update_flag=False,
                tenant_id=TENANT_ID,
                batch_id="SUPPLIER-SETTLEMENT-V84",
            )
        if created and record.status == "settlement_completed":
            transition_settlement_completion(
                completion, "completed", operator, "V84 供应商结算闭环确认"
            )

    completed = list(
        SupplierSettlementCompletion.objects.filter(status="completed")
    )
    for metric in SupplierPerformanceMetric.objects.all():
        sources = [
            item.settlement_no
            for item in completed
            if item.supplier_id == metric.supplier_id
        ]
        metric.completed_settlement_count = len(sources)
        metric.timely_payment_count = len(sources)
        metric.abnormal_settlement_count = 0
        metric.source_settlement_completion_nos = sources
        metric.save(update_fields=[
            "completed_settlement_count",
            "timely_payment_count",
            "abnormal_settlement_count",
            "source_settlement_completion_nos",
        ])
    all_sources = [item.settlement_no for item in completed]
    for metric in BuyerPerformanceMetric.objects.all():
        metric.payment_request_timeliness_rate = Decimal("100.00")
        metric.settlement_exception_rate = Decimal("0.00")
        metric.source_settlement_completion_nos = all_sources
        metric.save(update_fields=[
            "payment_request_timeliness_rate",
            "settlement_exception_rate",
            "source_settlement_completion_nos",
        ])
    return {
        "paymentStatusRecords": SupplierPaymentStatusRecord.objects.count(),
        "settlementCompletions": SupplierSettlementCompletion.objects.count(),
    }
